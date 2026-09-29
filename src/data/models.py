"""Typed records for orders, customers, requests, and recorded actions.

Money is Decimal dollars in these models (the database stores floats like 8.54; the store rounds each
value to two decimals and converts, so no float arithmetic happens downstream).
Dates and times are naive datetimes, read as US Pacific time (POL-02). Day counts use `.date()`.
Field meanings are documented in design/mock-data.md.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Tier = Literal["basic", "summit", "peak"]
Category = Literal[
    "apparel_footwear", "electronics", "hygiene_personal_care", "furniture_oversized", "perishables",
    "jewelry", "custom_personalized", "gift_card", "outdoor_gear", "home_goods",
]


class Item(BaseModel):
    item_id: str
    name: str
    category: Category
    price_paid: Decimal  # after any discount, before tax
    tax: Decimal
    is_set: bool = False
    tags: list[str] = Field(default_factory=list)  # may include "doorbuster", "clearance"
    final_sale_flag: bool = False
    final_sale_on_confirmation: bool = False
    is_oversized: bool = False


class Customer(BaseModel):
    customer_id: str
    first_name: str
    last_name: str
    email: str
    loyalty_tier_current: Tier
    returns_last_60d: int = 0
    refunded_last_60d: Decimal = Decimal("0")
    last_keep_it_refund_date: date | None = None


class Order(BaseModel):
    order_id: str
    customer_id: str
    order_date: datetime
    status: Literal["processing", "shipped", "delivered"]
    delivered_date: datetime | None = None  # the carrier's delivered scan, with time
    estimated_delivery_date: date | None = None
    ship_to_state: str
    loyalty_tier_at_purchase: Tier
    outbound_shipping_paid: Decimal = Decimal("0")
    items: list[Item]

    @model_validator(mode="after")
    def _check(self) -> "Order":
        if len(self.items) != 1:  # single-item orders only for now (D-024)
            raise ValueError("an order must have exactly one item")
        return self


class AgentRequest(BaseModel):
    order_id: str
    message: str  # untrusted customer text
    today: date  # always passed in; the agent never reads the system clock
    now: datetime | None = None  # only for the 48-hour cases

    @model_validator(mode="after")
    def _check(self) -> "AgentRequest":
        if self.now and self.now.date() != self.today:
            raise ValueError("now must fall on today")
        return self


class Action(BaseModel):
    """One thing the agent did during a run. Kept in memory, never persisted."""
    type: Literal["create_rma", "keep_it_refund", "cancel_order", "create_exchange", "open_escalation"]
    order_id: str
    item_id: str | None = None
    refund_amount: Decimal | None = None
    refund_method: Literal["original", "store_credit"] | None = None
    escalation_type: str | None = None
    reason: str | None = None
    docs_consulted: list[str] = Field(default_factory=list)
