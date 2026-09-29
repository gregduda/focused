"""Tests for the deterministic calculators. Run with:  pytest tests/tools
Expected values were worked out by hand from the formulas in the policy docs (POL-02, POL-07, POL-08, POL-11)."""
from datetime import date

import pytest

from src.tools.calculators import (
    CALCULATOR_TOOLS, Window, check_claim_window, check_elapsed_hours, compute_deadline, compute_refund,
)


# --- compute_deadline ---------------------------------------------------------------------------------

def test_deadline_last_day_is_inclusive():
    r = compute_deadline("2026-08-30", [Window(label="base", days=30)], "2026-09-29")
    assert r["applied_deadline"] == "2026-09-29" and r["within_window"] and r["days_remaining"] == 0


def test_deadline_one_day_late():
    r = compute_deadline("2026-08-29", [Window(label="base", days=30)], "2026-09-29")
    assert r["applied_deadline"] == "2026-09-28" and not r["within_window"] and r["days_remaining"] == -1


def test_windows_do_not_stack_latest_wins():
    windows = [Window(label="base", days=30), Window(label="Peak", days=60),
               Window(label="WA", days=45), Window(label="Fall Gear-Up", days=45)]
    r = compute_deadline("2026-09-08T15:00:00", windows, "2026-11-10")
    assert r["applied_label"] == "Peak" and r["applied_deadline"] == "2026-11-07"
    assert not r["within_window"] and r["days_since_start"] == 63


def test_fixed_date_window_competes_with_day_windows():
    windows = [Window(label="base", days=30), Window(label="Holiday", fixed_date=date(2027, 1, 31))]
    late_delivery = compute_deadline("2027-01-25", windows, "2027-02-10")
    assert late_delivery["applied_label"] == "base" and late_delivery["applied_deadline"] == "2027-02-24"
    early_delivery = compute_deadline("2026-12-14", windows, "2027-01-20")
    assert early_delivery["applied_label"] == "Holiday" and early_delivery["within_window"]


def test_window_needs_exactly_one_of_days_or_fixed_date():
    with pytest.raises(ValueError):
        Window(label="bad")
    with pytest.raises(ValueError):
        Window(label="bad", days=5, fixed_date=date(2026, 1, 1))


# --- compute_refund -----------------------------------------------------------------------------------

def test_refund_electronics_california_opened():
    r = compute_refund(200.00, 17.00, restocking_pct=10, label_fee=7.95)
    assert r["restocking_fee"] == "20.00" and r["fees_total"] == "27.95" and r["refund_total"] == "189.05"


def test_refund_electronics_texas_opened():
    assert compute_refund(200.00, 17.00, restocking_pct=15, label_fee=7.95)["refund_total"] == "179.05"


def test_refund_fees_waived():
    assert compute_refund(200.00, 17.00)["refund_total"] == "217.00"


def test_refund_furniture_pickup_and_restocking():
    r = compute_refund(180.00, 14.40, restocking_pct=20, pickup_fee=75)
    assert r["fees_total"] == "111.00" and r["refund_total"] == "83.40"


def test_refund_includes_shipping_when_passed():
    assert compute_refund(120.00, 9.60, outbound_shipping_refund=9.95)["refund_total"] == "139.55"


def test_refund_store_credit_bonus_rounds_half_up():
    r = compute_refund(120.00, 9.60, label_fee=7.95, store_credit_bonus_pct=5)
    assert r["refund_total"] == "121.65" and r["store_credit_bonus"] == "6.08" and r["total_to_customer"] == "127.73"


def test_refund_percentage_fee_rounds_half_up():
    assert compute_refund(10.10, 0, restocking_pct=15)["restocking_fee"] == "1.52"  # 1.515 -> 1.52


def test_refund_can_go_negative_and_says_so():
    r = compute_refund(5.00, 0.40, label_fee=7.95)
    assert r["refund_total"] == "-2.55" and r["refund_is_negative"]


def test_refund_rejects_bad_input():
    with pytest.raises(ValueError):
        compute_refund(-1, 0)
    with pytest.raises(ValueError):
        compute_refund(10, 0, restocking_pct=150)


# --- check_claim_window -------------------------------------------------------------------------------

def test_claim_window_eligible_after_five_business_days():
    r = check_claim_window("2026-09-18", "2026-09-29", 5, 30)  # estimated Fri Sep 18
    assert r["earliest_claim_date"] == "2026-09-25" and r["status"] == "eligible"


def test_claim_window_too_early():
    r = check_claim_window("2026-09-25", "2026-09-29", 5, 30)  # estimated Fri Sep 25
    assert r["earliest_claim_date"] == "2026-10-02" and r["status"] == "too_early"


def test_claim_window_too_late():
    r = check_claim_window("2026-08-01", "2026-09-29", 5, 30)
    assert r["latest_claim_date"] == "2026-08-31" and r["status"] == "too_late"


def test_claim_window_skips_weekends():
    assert check_claim_window("2026-09-19", "2026-09-29", 1, 30)["earliest_claim_date"] == "2026-09-21"  # Sat -> Mon


# --- check_elapsed_hours ------------------------------------------------------------------------------

def test_elapsed_hours_within_limit():
    r = check_elapsed_hours("2026-09-28T06:00:00", "2026-09-29T12:00:00", 48)
    assert r["hours_elapsed"] == "30.00" and r["within_limit"] and not r["limit_reached"]


def test_elapsed_hours_past_limit():
    r = check_elapsed_hours("2026-09-26T00:00:00", "2026-09-28T12:00:00", 48)
    assert r["hours_elapsed"] == "60.00" and not r["within_limit"] and r["limit_reached"]


def test_elapsed_hours_exactly_at_limit_is_both():
    r = check_elapsed_hours("2026-09-27T12:00:00", "2026-09-29T12:00:00", 48)
    assert r["within_limit"] and r["limit_reached"]


def test_elapsed_hours_rejects_reversed_times():
    with pytest.raises(ValueError):
        check_elapsed_hours("2026-09-29T12:00:00", "2026-09-28T12:00:00", 48)


# --- as LLM tools -------------------------------------------------------------------------------------

def test_tools_are_callable_with_json_style_arguments():
    by_name = {t.name: t for t in CALCULATOR_TOOLS}
    assert set(by_name) == {"compute_deadline", "compute_refund", "check_claim_window", "check_elapsed_hours"}
    r = by_name["compute_deadline"].invoke({
        "start": "2026-08-30", "today": "2026-09-29",
        "windows": [{"label": "base", "days": 30}, {"label": "holiday", "fixed_date": "2027-01-31"}],
    })
    assert r["applied_label"] == "holiday"
    assert by_name["compute_refund"].invoke({"price_paid": 200, "tax": 17, "label_fee": 7.95})["refund_total"] == "209.05"
