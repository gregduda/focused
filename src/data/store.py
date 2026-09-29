"""Read-only access to the mock order database, plus the in-memory list of actions taken in one run.

Create the database first (see design/mock-data.md):
    sqlite3 data/orders.db < data/schema.sql && sqlite3 data/orders.db < data/seed.sql
"""
import os
import sqlite3
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

from src.data.models import Action, Customer, Item, Order

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / os.environ["ORDERS_DB_PATH"]


def _dollars(amount: float | None) -> Decimal | None:
    """Database floats (e.g. 8.54) to two-decimal Decimal, so later arithmetic is exact."""
    return None if amount is None else Decimal(str(round(amount, 2))).quantize(Decimal("0.01"))


class OrderStore:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        # mode=ro: the connection cannot write, so a run cannot change the data.
        self._conn = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row
        self.actions: list[Action] = []

    def get_order(self, order_id: str) -> Order | None:
        row = self._conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            return None
        items = self._conn.execute("SELECT * FROM items WHERE order_id = ? ORDER BY item_id", (order_id,)).fetchall()
        return Order(
            order_id=row["order_id"],
            customer_id=row["customer_id"],
            order_date=row["order_date"],
            status=row["status"],
            delivered_date=row["delivered_date"],
            estimated_delivery_date=row["estimated_delivery_date"],
            ship_to_state=row["ship_to_state"],
            loyalty_tier_at_purchase=row["loyalty_tier_at_purchase"],
            outbound_shipping_paid=_dollars(row["outbound_shipping_paid"]),
            items=[
                Item(
                    item_id=i["item_id"], name=i["name"], category=i["category"],
                    price_paid=_dollars(i["price_paid"]), tax=_dollars(i["tax"]),
                    is_set=bool(i["is_set"]),
                    tags=[t for t in i["tags"].split(",") if t],
                    final_sale_flag=bool(i["final_sale_flag"]),
                    final_sale_on_confirmation=bool(i["final_sale_on_confirmation"]),
                    is_oversized=bool(i["is_oversized"]),
                )
                for i in items
            ],
        )

    def get_customer(self, customer_id: str) -> Customer:
        row = self._conn.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
        return Customer(
            customer_id=row["customer_id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=row["email"],
            loyalty_tier_current=row["loyalty_tier_current"],
            returns_last_60d=row["returns_last_60d"],
            refunded_last_60d=_dollars(row["refunded_last_60d"]),
            last_keep_it_refund_date=row["last_keep_it_refund_date"],
        )

    def record_action(self, action: Action) -> None:
        self.actions.append(action)
