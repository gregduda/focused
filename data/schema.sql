-- Mock order database for the refund agent. Read-only at run time (see src/data/store.py).
-- Money is REAL dollars, e.g. 8.54. Dates and times are ISO text (YYYY-MM-DDTHH:MM:SS), naive, read as
-- US Pacific time (POL-02 sets deadlines in Pacific). Booleans are 0 or 1.
-- Each order has exactly one item for now (D-024).

DROP TABLE IF EXISTS items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id               TEXT PRIMARY KEY,
    first_name                TEXT NOT NULL,
    last_name                 TEXT NOT NULL,
    email                     TEXT NOT NULL,
    loyalty_tier_current      TEXT NOT NULL CHECK (loyalty_tier_current IN ('basic', 'summit', 'peak')),
    returns_last_60d          INTEGER NOT NULL DEFAULT 0,
    refunded_last_60d         REAL NOT NULL DEFAULT 0,
    last_keep_it_refund_date  TEXT  -- date only, YYYY-MM-DD
);

CREATE TABLE orders (
    order_id                  TEXT PRIMARY KEY,
    customer_id               TEXT NOT NULL REFERENCES customers (customer_id),
    order_date                TEXT NOT NULL,  -- date and time
    status                    TEXT NOT NULL CHECK (status IN ('processing', 'shipped', 'delivered')),
    delivered_date            TEXT,           -- date and time of the carrier's "delivered" scan
    estimated_delivery_date   TEXT,           -- date only, YYYY-MM-DD
    ship_to_state             TEXT NOT NULL,
    loyalty_tier_at_purchase  TEXT NOT NULL CHECK (loyalty_tier_at_purchase IN ('basic', 'summit', 'peak')),
    outbound_shipping_paid    REAL NOT NULL DEFAULT 0,
    CHECK ((status = 'delivered') = (delivered_date IS NOT NULL))
);

CREATE TABLE items (
    item_id                    TEXT PRIMARY KEY,
    order_id                   TEXT NOT NULL REFERENCES orders (order_id),
    name                       TEXT NOT NULL,
    category                   TEXT NOT NULL CHECK (category IN (
        'apparel_footwear', 'electronics', 'hygiene_personal_care', 'furniture_oversized', 'perishables',
        'jewelry', 'custom_personalized', 'gift_card', 'outdoor_gear', 'home_goods')),
    price_paid                 REAL NOT NULL,  -- after any discount, before tax
    tax                        REAL NOT NULL,
    is_set                     INTEGER NOT NULL DEFAULT 0,
    tags                       TEXT NOT NULL DEFAULT '',  -- comma separated: doorbuster, clearance
    final_sale_flag            INTEGER NOT NULL DEFAULT 0,
    final_sale_on_confirmation INTEGER NOT NULL DEFAULT 0,
    is_oversized               INTEGER NOT NULL DEFAULT 0
);
