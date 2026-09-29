# Mock data and store (proposal, not built)

Status: design settled (D-022 to D-024); nothing here is implemented yet.

## What this is for
The agent needs orders and customers to reason about. There is no real order system, so we fake one, kept as small as possible:

- **A read-only SQLite database** (`orders.db`) with three tables: `customers`, `orders`, `items`. The agent looks orders up by `order_id`. Python's built-in `sqlite3` is enough: no server, no extra install.
- **Never updated by a run.** The store opens the file in read-only mode (`file:orders.db?mode=ro`), so a run physically cannot change it. Evals are therefore repeatable.
- **Actions live in memory.** When the agent calls an action tool (create RMA, escalate, ...), the tool appends a record to a Python list for that run. The evals read the list and it is discarded. Nothing about actions is written to the database or to a file. (The LangSmith trace also shows every tool call.)
- **The database is the single source of truth.** It is created from two SQL text files (`schema.sql`, `seed.sql`). There is no second copy of the data in Python. The reference oracle reads the rows straight from the database, builds Pydantic objects, and computes expected dates and amounts, so those values still come from code.

No Postgres, no files written per run.

## Proposed files
```
data/schema.sql           CREATE TABLE statements for customers, orders, items
data/seed.sql             INSERT statements: demo orders plus one group per eval case's order
data/orders.db            created with: sqlite3 data/orders.db < data/schema.sql < ... (see README)
src/data/models.py        Pydantic models: Order, Item, Customer, AgentRequest, Action
src/data/store.py         OrderStore: read-only sqlite3 wrapper returning models, plus the in-memory actions list
```

## Records

### AgentRequest (what a run receives)
| Field | Type | Notes |
|---|---|---|
| `order_id` | str | Structured input. Never read from the message. |
| `message` | str | Untrusted customer text (OPS-07). |
| `today` | date | Passed on every run. Never the system clock. |
| `now` | datetime or null | Only for the 48-hour cases (perishables, delivered but not received). Its date must equal `today`; the loader checks. |

### Order
| Field | Type | Used by |
|---|---|---|
| `order_id` | str | lookup key |
| `customer_id` | str | links to Customer |
| `order_date` | datetime | Fall Gear-Up and holiday programs (SEA-02, SEA-05) |
| `status` | `processing`, `shipped`, `delivered` | cancellation (POL-14) |
| `delivered_date` | datetime or null | carrier's delivered scan, with time. Return window (POL-02, counted by calendar day), Florida (ST-FL), and the 48-hour rules |
| `estimated_delivery_date` | date or null | lost-package rule (POL-11). Not in the corpus README. |
| `ship_to_state` | 2-letter str | state addenda (ST-*) |
| `loyalty_tier_at_purchase` | `basic`, `summit`, `peak` | LOY-01 |
| `outbound_shipping_paid` | decimal | shipping refund (POL-08). Not in the corpus README. |
| `items` | list of Item | exactly one item per order for now (D-024) |

### Item
| Field | Type | Used by |
|---|---|---|
| `item_id`, `name` | str | |
| `category` | one of the 10 category keys | CAT-* |
| `price_paid` | decimal | after any discount, before tax. Fees are a percent of this. |
| `tax` | decimal | input, never computed (POL-08) |
| `is_set` | bool | POL-09 |
| `tags` | list, may contain `doorbuster`, `clearance` | SEA-03, SEA-04 |
| `final_sale_flag` | bool | POL-15 |
| `final_sale_on_confirmation` | bool | ST-NY |
| `is_oversized` | bool | furniture, over 50 lb or longer than 72 in (CAT-04). Not in the README. |

### Customer
| Field | Type | Used by |
|---|---|---|
| `customer_id`, `first_name`, `last_name`, `email` | str | names for greeting the customer; email only for masking rules in messages (OPS-02) |
| `loyalty_tier_current` | tier | exists to trap the "use the tier at purchase" mistake (case A3) |
| `returns_last_60d` | int | OPS-03 (4 or more escalates) |
| `refunded_last_60d` | decimal | OPS-03 ($1,000 or more escalates) |
| `last_keep_it_refund_date` | date or null | POL-11 (one per 90 days) |

### Not stored on the order: what the customer says
The customer's stated condition (unopened, worn, used) and reason code (`CHANGED_MIND`, `DEFECTIVE`, ...) come from the message. The agent extracts them, and the reason code goes into its structured output. This is deliberate: reading them correctly is part of what we evaluate.

## Database layout
Three tables, one row per record, matching the field tables above.

| Table | Key | Notes |
|---|---|---|
| `customers` | `customer_id` | tier now, returns and refunds in the last 60 days, last keep-it refund date |
| `orders` | `order_id` | one row per order; `customer_id` links to `customers` |
| `items` | `item_id` | one row per line item; `order_id` links to `orders`; `tags` stored as a comma-separated string |

Storage conventions, chosen to avoid classic bugs:
- **Money as floats** with two decimals (`price_paid` 120.00, `tax` 9.60). The store rounds each value to two decimals and converts it to `Decimal` when building the models, so the calculators never do float arithmetic. Rounding is done once, in the calculators (POL-08: half up).
- **`order_date` and `delivered_date` as ISO date-times** (`2026-09-29T14:30:00`), naive and read as US Pacific time (POL-02 sets deadlines in Pacific). The window logic uses the calendar date part. `estimated_delivery_date` and `last_keep_it_refund_date` stay date-only.
- **Booleans as 0 or 1.**
- No foreign-key trickery, no indexes beyond the primary keys; the tables hold tens of rows.

## The store
```python
class OrderStore:
    def __init__(self, db_path)                  # opens read-only
    def get_order(order_id) -> Order | None      # joins items
    def get_customer(customer_id) -> Customer
    def record_action(action: Action) -> None    # appends to the in-memory list
    actions: list[Action]                        # what happened during this run
```
An unknown `order_id` returns `None`. Proposed behavior: ESCALATE with a message that the order could not be found (consistent with D-006, three labels only).

## Actions the agent can record
| `type` | Fields | Corpus source |
|---|---|---|
| `create_rma` | order_id, item_ids, refund_amount, refund_method (`original` or `store_credit`) | POL-01, OPS-01 |
| `keep_it_refund` | order_id, item_id, refund_amount | POL-11 |
| `cancel_order` | order_id, refund_amount | POL-14 |
| `create_exchange` | order_id, item_id | POL-13 |
| `open_escalation` | order_id, escalation_type, reason, docs_consulted | OPS-01 |

`escalation_type` values: `standard`, `warranty`, `loss_prevention`, `safety`, `goodwill`, `missing_package`, `high_value`. These are our own labels, useful for slicing eval results; the corpus names only some of them. The corpus says an escalation hand-off includes the order number, the request, the policy documents consulted, and the reason (OPS-01), which is why those fields are there.

Refunds are only issued after the warehouse inspects the item (POL-04), except keep-it refunds. So `create_rma` records the amount the customer will receive; it does not move money.

## Eval case shape
A case points at an order that exists in `orders.db`:
```json
{
  "case_id": "window-apparel-day31",
  "request": {"order_id": "T-0042", "message": "...", "today": "2026-09-29"},
  "expected": {
    "decision": "DENY",
    "refund_amount": null,
    "expected_actions": [],
    "gold_doc_ids": ["POL-02", "CAT-01"]
  },
  "slices": {"category": "apparel_footwear", "state": "TX", "tier": "basic", "season": "none"}
}
```
`expected.refund_amount` and every date are computed by reference-oracle code from the order's database rows, never typed by hand or generated by an LLM.

Tradeoffs to know about:
- The database stores absolute dates ("delivered 2026-08-29"), not "31 days ago". Because `today` is passed with every case, that is reproducible, but whoever writes the seed rows must compute each date correctly. A throwaway check script will recompute each case's day count from the rows to catch slips.
- A case in LangSmith shows only `order_id`. When the dataset is uploaded, the upload script can copy a readable snapshot of the order into each example's metadata for display; the agent itself only reads the database.

## Resolved questions (D-024)
1. **Hour-level rules:** add `now` on the request; `delivered_date` on the order now carries the time of day (there is no separate `delivered_at` column).
2. **Multi-item orders:** single-item orders only for now. Each order has exactly one item. The `items` table stays (one row per order) so multi-item can be added later without changing the schema.
3. **Unknown order id:** the store returns `None` and the agent ESCALATES with a message that the order could not be found.

Cases dropped by going single-item: B17 and B18 (spend threshold and code proration), B19 (one label for two items). POL-09's threshold and proration rules stay in the corpus but are not evaluated.
