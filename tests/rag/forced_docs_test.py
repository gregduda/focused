"""Tests for the documents the experimental retrieval modes add by rule. Run with:  pytest tests/rag

The first group needs no index. The last test reads the Chroma index (build it first: python -m src.rag.embed_sources)."""
from datetime import datetime
from decimal import Decimal

import pytest

from src.data.models import Customer, Item, Order
from src.rag.chunk_retriever import docs_by_id
from src.rag.forced_docs import CORE_DOCS, forced_doc_ids


def make(category="apparel_footwear", state="TX", ordered="2026-08-20T10:00:00", tags=(), tier_at="basic",
         tier_now="basic") -> tuple[Order, Customer]:
    item = Item(item_id="i", name="x", category=category, price_paid=Decimal("10"), tax=Decimal("1"), tags=list(tags))
    order = Order(order_id="o", customer_id="c", order_date=datetime.fromisoformat(ordered), status="processing",
                  ship_to_state=state, loyalty_tier_at_purchase=tier_at, items=[item])
    customer = Customer(customer_id="c", first_name="a", last_name="b", email="a@b.c", loyalty_tier_current=tier_now)
    return order, customer


def test_v1_adds_nothing_and_core_adds_the_fixed_list():
    order, customer = make()
    assert forced_doc_ids("v1", order, customer) == []
    assert forced_doc_ids("core", order, customer) == CORE_DOCS


def test_core_order_adds_the_category_and_state_documents():
    ids = forced_doc_ids("core_order", *make(category="electronics", state="WA"))
    assert ids[:len(CORE_DOCS)] == CORE_DOCS and "CAT-02" in ids and "ST-WA" in ids
    assert not {"SEA-02", "SEA-03", "SEA-04", "SEA-05", "LOY-01"} & set(ids)


def test_a_state_without_an_addendum_gets_the_overview():
    ids = forced_doc_ids("core_order", *make(state="OH"))
    assert "ST-00" in ids and not any(i.startswith("ST-") and i != "ST-00" for i in ids)


@pytest.mark.parametrize("ordered,expected", [("2026-09-01T00:00:00", "SEA-05"), ("2026-10-15T23:00:00", "SEA-05"),
                                              ("2026-10-16T00:00:00", None), ("2026-11-01T09:00:00", "SEA-02"),
                                              ("2026-12-24T23:00:00", "SEA-02"), ("2026-12-25T00:00:00", None)])
def test_seasonal_documents_follow_the_order_date(ordered, expected):
    ids = forced_doc_ids("core_order", *make(ordered=ordered))
    assert {"SEA-05", "SEA-02"} & set(ids) == ({expected} if expected else set())


def test_item_tags_and_tiers_add_their_documents():
    ids = forced_doc_ids("core_order", *make(tags=["doorbuster", "clearance"]))
    assert {"SEA-03", "SEA-04"} <= set(ids) and "LOY-01" not in ids
    assert "LOY-01" in forced_doc_ids("core_order", *make(tier_at="summit"))
    assert "LOY-01" in forced_doc_ids("core_order", *make(tier_now="peak"))  # the tier-at-purchase trap needs LOY-01


def test_an_unknown_mode_is_an_error():
    with pytest.raises(ValueError):
        forced_doc_ids("everything", *make())


def test_docs_by_id_returns_every_chunk_of_the_requested_documents_in_order():
    chunks = docs_by_id(["POL-08", "OPS-01"])
    ids = [c.metadata["doc_id"] for c in chunks]
    assert set(ids) == {"POL-08", "OPS-01"} and ids == sorted(ids, key=["POL-08", "OPS-01"].index)
    assert all(c.metadata["distance"] == 0.0 and c.page_content.startswith(c.metadata["title"]) for c in chunks)


def test_the_seasonal_calendar_is_in_the_core_set():
    assert "SEA-01" in CORE_DOCS
