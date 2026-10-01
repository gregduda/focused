"""Documents added to the agent's context by rule, not by search (retrieval modes `core` and `core_order`, D-067).

v1 (the default) searches with the customer's message alone. Two experiments add documents on top of that search:

  core        the documents every request is evaluated with, taken from the order of evaluation in POL-07:
              eligibility gates (POL-15, POL-03), deadline and stacking (POL-02, POL-07, and SEA-01,
              the seasonal calendar, because step 2 is to list every window that applies and the agent needs the
              program dates to rule one in or out, D-089), fees (POL-05, POL-06),
              refund amount (POL-08), escalation (OPS-01), plus the agent-operations rules (OPS-03, OPS-06, OPS-07).
  core_order  core, plus the documents the order record itself points to: the category document, the state
              addendum (ST-00 when the state has none), the seasonal program the order date or item tags fall in,
              and the loyalty document when either tier is above Basic.

Only order facts decide this, never the customer's message, which is untrusted text. The rules themselves stay in
the documents; this only decides which documents the model gets to read.
"""
from datetime import date

from src.data.models import Customer, Order

CORE_DOCS = ["POL-02", "POL-03", "POL-05", "POL-06", "POL-07", "POL-08", "POL-15", "SEA-01", "OPS-01", "OPS-03",
             "OPS-06", "OPS-07"]

CATEGORY_DOC = {
    "apparel_footwear": "CAT-01", "electronics": "CAT-02", "hygiene_personal_care": "CAT-03",
    "furniture_oversized": "CAT-04", "perishables": "CAT-05", "jewelry": "CAT-06", "custom_personalized": "CAT-07",
    "gift_card": "CAT-08", "outdoor_gear": "CAT-09", "home_goods": "CAT-10",
}
STATES_WITH_ADDENDUM = {"CA", "FL", "IL", "MA", "NY", "TX", "WA"}

# Order-date windows of the 2026 seasonal programs, from SEA-01. Only a routing table: the rules are in the SEA docs.
FALL_GEAR_UP = (date(2026, 9, 1), date(2026, 10, 15))
HOLIDAY = (date(2026, 11, 1), date(2026, 12, 24))

MODES = ("v1", "core", "core_order")


def forced_doc_ids(mode: str, order: Order, customer: Customer) -> list[str]:
    """The document ids to add for this order under the given retrieval mode (none for v1)."""
    if mode not in MODES:
        raise ValueError(f"unknown retrieval mode {mode!r}; expected one of {MODES}")
    if mode == "v1":
        return []
    ids = list(CORE_DOCS)
    if mode == "core":
        return ids

    item, ordered = order.items[0], order.order_date.date()
    ids.append(CATEGORY_DOC[item.category])
    ids.append(f"ST-{order.ship_to_state}" if order.ship_to_state in STATES_WITH_ADDENDUM else "ST-00")
    if FALL_GEAR_UP[0] <= ordered <= FALL_GEAR_UP[1]:
        ids.append("SEA-05")
    if HOLIDAY[0] <= ordered <= HOLIDAY[1]:
        ids.append("SEA-02")
    if "doorbuster" in item.tags:
        ids.append("SEA-03")
    if "clearance" in item.tags:
        ids.append("SEA-04")
    if "basic" != order.loyalty_tier_at_purchase or customer.loyalty_tier_current != "basic":
        ids.append("LOY-01")
    return ids
