"""Tests for the mock order store. Run with:  pytest tests/data
Needs the database created first (see src/data/store.py)."""
import sqlite3
from datetime import date, datetime
from decimal import Decimal

import pytest

from src.data.models import Action, AgentRequest
from src.data.store import DEFAULT_DB_PATH, OrderStore


@pytest.fixture
def store():
    return OrderStore()


def test_get_order_returns_typed_record(store):
    order = store.get_order("JP-1001")
    assert order.ship_to_state == "TX"
    assert order.delivered_date == datetime(2026, 9, 10, 14, 30)
    assert order.order_date == datetime(2026, 9, 6, 9, 12)
    item = order.items[0]
    assert item.price_paid == Decimal("120.00") and item.tax == Decimal("9.60")


def test_unknown_order_returns_none(store):
    assert store.get_order("NOPE") is None


def test_customer_and_tier_at_purchase(store):
    order = store.get_order("JP-1003")
    customer = store.get_customer(order.customer_id)
    assert order.loyalty_tier_at_purchase == "summit"
    assert (customer.first_name, customer.last_name) == ("Sam", "Chen")
    assert customer.returns_last_60d == 1 and customer.refunded_last_60d == Decimal("85.00")


def test_all_seed_orders_load(store):
    conn = sqlite3.connect(f"file:{DEFAULT_DB_PATH}?mode=ro", uri=True)
    ids = [r[0] for r in conn.execute("SELECT order_id FROM orders")]
    assert len(ids) == 11
    for order_id in ids:
        assert store.get_order(order_id) is not None


def test_database_is_read_only(store):
    with pytest.raises(sqlite3.OperationalError):
        store._conn.execute("DELETE FROM orders")


def test_actions_are_kept_in_memory_only(store):
    store.record_action(Action(type="open_escalation", order_id="JP-1001", reason="test"))
    assert len(store.actions) == 1
    assert len(OrderStore().actions) == 0  # a new run starts empty


def test_money_is_exact_decimal(store):
    item = store.get_order("JP-1008").items[0]
    assert item.tax == Decimal("7.99") and item.price_paid + item.tax == Decimal("97.99")


def test_request_now_must_match_today():
    with pytest.raises(ValueError):
        AgentRequest(order_id="x", message="hi", today=date(2026, 9, 29), now=datetime(2026, 9, 30, 8, 0))
    AgentRequest(order_id="x", message="hi", today=date(2026, 9, 29), now=datetime(2026, 9, 29, 12, 0))
