"""Deterministic calculators the agent calls as tools.

They contain arithmetic and calendar logic only, no policy. The LLM reads the policy from the retrieved
documents and passes the numbers in (window days, fee percentages, which fees apply). Every amount and
date the agent states should come out of one of these functions (hard rule 3).

Conventions:
- Dates come in as ISO strings ("2026-09-29" or "2026-09-29T14:30:00"); only the calendar date is used
  except in check_elapsed_hours.
- Money comes in as numbers, is converted to Decimal, and goes out as two-decimal strings ("189.05").
- Percentage fees and bonuses round half up (POL-08).
- Bad input raises ValueError; the tool framework returns that message to the LLM.
"""
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from langchain_core.tools import tool
from pydantic import BaseModel, model_validator

CENT = Decimal("0.01")


def _money(x: float | Decimal) -> Decimal:
    return Decimal(str(x))


def _round(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def _date(s: str) -> date:
    return datetime.fromisoformat(s).date()


class Window(BaseModel):
    """One candidate deadline: either a number of days from the start date, or a fixed calendar date."""
    label: str  # for example "Peak tier 60 days" or "Holiday deadline"
    days: int | None = None
    fixed_date: date | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "Window":
        if (self.days is None) == (self.fixed_date is None):
            raise ValueError("give exactly one of days or fixed_date")
        return self


def compute_deadline(start: str, windows: list[Window], today: str) -> dict:
    """Work out which deadline applies and whether today is on or before it.

    start: the date the clock starts (for a return, the delivery date). Day 0 is the start date.
    windows: every candidate window that applies; each is a number of days from the start or a fixed date.
      Windows never add together: the LATEST resulting deadline is the one applied.
    today: the current date, passed in with the request.
    The last eligible day is the deadline itself (inclusive).
    """
    start_d, today_d = _date(start), _date(today)
    candidates = []
    for w in windows:
        deadline = start_d + timedelta(days=w.days) if w.days is not None else w.fixed_date
        candidates.append({"label": w.label, "deadline": deadline})
    if not candidates:
        raise ValueError("at least one window is required")
    applied = max(candidates, key=lambda c: c["deadline"])
    return {
        "start_date": start_d.isoformat(),
        "today": today_d.isoformat(),
        "days_since_start": (today_d - start_d).days,
        "candidates": [{"label": c["label"], "deadline": c["deadline"].isoformat()} for c in candidates],
        "applied_label": applied["label"],
        "applied_deadline": applied["deadline"].isoformat(),
        "within_window": today_d <= applied["deadline"],
        "days_remaining": (applied["deadline"] - today_d).days,  # negative once past
    }


def compute_refund(
    price_paid: float,
    tax: float,
    restocking_pct: float = 0,
    label_fee: float = 0,
    pickup_fee: float = 0,
    outbound_shipping_refund: float = 0,
    store_credit_bonus_pct: float = 0,
) -> dict:
    """Compute the refund. Refund = price paid + tax + shipping refunded - fees.

    price_paid: what the customer paid for the item, before tax. Restocking is a percentage of this.
    tax: sales tax on the item (refunded in full).
    restocking_pct: restocking fee percent, 0 if none or waived (for example 15, or 10 in California).
    label_fee: return label fee in dollars, 0 if none or waived.
    pickup_fee: freight pickup fee in dollars, 0 if none or waived.
    outbound_shipping_refund: original shipping charge to refund, 0 if not refundable.
    store_credit_bonus_pct: bonus percent on the refund total if the customer chooses store credit, else 0.
    Pass 0 for anything that does not apply. Returns two-decimal strings.
    """
    if any(v < 0 for v in (price_paid, tax, restocking_pct, label_fee, pickup_fee, outbound_shipping_refund,
                           store_credit_bonus_pct)):
        raise ValueError("inputs must not be negative")
    if restocking_pct > 100 or store_credit_bonus_pct > 100:
        raise ValueError("percentages must be between 0 and 100")

    price, tax_d = _money(price_paid), _money(tax)
    restocking = _round(price * _money(restocking_pct) / 100)
    fees_total = restocking + _money(label_fee) + _money(pickup_fee)
    refund_total = price + tax_d + _money(outbound_shipping_refund) - fees_total
    bonus = _round(refund_total * _money(store_credit_bonus_pct) / 100)
    return {
        "price_paid": str(_round(price)),
        "tax_refunded": str(_round(tax_d)),
        "shipping_refunded": str(_round(_money(outbound_shipping_refund))),
        "restocking_fee": str(restocking),
        "label_fee": str(_round(_money(label_fee))),
        "pickup_fee": str(_round(_money(pickup_fee))),
        "fees_total": str(_round(fees_total)),
        "refund_total": str(_round(refund_total)),
        "refund_is_negative": refund_total < 0,
        "store_credit_bonus": str(bonus),
        "total_to_customer": str(_round(refund_total + bonus)),
    }


def _add_business_days(start: date, n: int) -> date:
    """Add n business days (Monday to Friday, no holiday calendar)."""
    d = start
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def check_claim_window(start_date: str, today: str, wait_business_days: int, max_calendar_days: int) -> dict:
    """Check a claim that can only be filed after a wait and before a cutoff (for example a lost package).

    start_date: the date the wait counts from (for a lost package, the estimated delivery date).
    wait_business_days: business days that must pass first (Monday to Friday, no holidays). The claim can be
      filed starting on the date that many business days after start_date.
    max_calendar_days: last day to file, counted in calendar days from start_date (inclusive).
    Returns status "too_early", "eligible", or "too_late".
    """
    start_d, today_d = _date(start_date), _date(today)
    earliest = _add_business_days(start_d, wait_business_days)
    latest = start_d + timedelta(days=max_calendar_days)
    status = "too_early" if today_d < earliest else "too_late" if today_d > latest else "eligible"
    return {
        "earliest_claim_date": earliest.isoformat(),
        "latest_claim_date": latest.isoformat(),
        "today": today_d.isoformat(),
        "status": status,
    }


def check_elapsed_hours(start: str, now: str, limit_hours: float) -> dict:
    """Hours between two timestamps, compared to a limit (for example 48 hours after delivery).

    start: ISO timestamp the clock starts from (for example the delivery time).
    now: ISO timestamp of the current moment, passed in with the request.
    within_limit is true when the elapsed hours are at most the limit ("report within 48 hours").
    limit_reached is true when the elapsed hours are at least the limit ("wait 48 hours first").
    """
    start_dt, now_dt = datetime.fromisoformat(start), datetime.fromisoformat(now)
    elapsed = Decimal(str((now_dt - start_dt).total_seconds())) / 3600
    if elapsed < 0:
        raise ValueError("now is before start")
    limit = _money(limit_hours)
    return {
        "hours_elapsed": str(_round(elapsed)),
        "limit_hours": str(limit),
        "within_limit": elapsed <= limit,
        "limit_reached": elapsed >= limit,
    }


# The tools handed to the agent. The plain functions above stay directly callable for tests and the oracle.
compute_deadline_tool = tool(compute_deadline)
compute_refund_tool = tool(compute_refund)
check_claim_window_tool = tool(check_claim_window)
check_elapsed_hours_tool = tool(check_elapsed_hours)
CALCULATOR_TOOLS = [compute_deadline_tool, compute_refund_tool, check_claim_window_tool, check_elapsed_hours_tool]
