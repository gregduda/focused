-- Demo orders. Convention: the demo "today" is 2026-09-29. Eval cases pass their own `today`.
-- Every order has one item. Day N = calendar days after the delivered date.

INSERT INTO customers VALUES
 -- customer_id, first_name, last_name, email, tier_now, returns_last_60d, refunded_last_60d, last_keep_it_refund_date
 ('C-001', 'Alex', 'Rivera', 'alex.rivera@example.com', 'basic',  0,   0.00, NULL),
 ('C-002', 'Sam',  'Chen',   'sam.chen@example.com',    'summit', 1,  85.00, NULL),
 ('C-003', 'Jo',   'Patel',  'jo.patel@example.com',    'peak',   2, 450.00, NULL),
 ('C-004', 'Lee',  'Kim',    'lee.kim@example.com',     'basic',  4, 320.00, NULL);

INSERT INTO orders VALUES
 -- order_id, customer_id, order_date, status, delivered_date, estimated_delivery_date,
 -- ship_to_state, tier_at_purchase, outbound_shipping_paid
 ('JP-1001', 'C-001', '2026-09-06T09:12:00', 'delivered',  '2026-09-10T14:30:00', '2026-09-11', 'TX', 'basic',  9.95),  -- apparel, day 19
 ('JP-1002', 'C-001', '2026-09-12T18:40:00', 'delivered',  '2026-09-15T11:05:00', '2026-09-16', 'CA', 'basic',  9.95),  -- electronics, day 14
 ('JP-1003', 'C-002', '2026-08-22T07:55:00', 'delivered',  '2026-08-25T16:20:00', '2026-08-26', 'MA', 'summit', 0.00),  -- furniture, day 35
 ('JP-1004', 'C-001', '2026-08-22T20:10:00', 'delivered',  '2026-08-26T13:45:00', '2026-08-27', 'FL', 'basic',  9.95),  -- home goods, day 34
 ('JP-1005', 'C-001', '2026-09-26T12:00:00', 'delivered',  '2026-09-28T18:00:00', '2026-09-28', 'TX', 'basic',  9.95),  -- perishable, 18h before 2026-09-29T12:00
 ('JP-1006', 'C-003', '2026-08-28T10:30:00', 'delivered',  '2026-09-01T15:15:00', '2026-09-02', 'WA', 'peak',    0.00),  -- outdoor gear, day 28
 ('JP-1007', 'C-001', '2026-09-28T08:05:00', 'processing', NULL,                  '2026-10-02', 'TX', 'basic',  9.95),  -- not shipped yet
 ('JP-1008', 'C-001', '2026-08-10T21:20:00', 'delivered',  '2026-08-15T12:10:00', '2026-08-16', 'NY', 'basic',  9.95),  -- clearance, not on confirmation; use a "today" near Aug 28
 ('JP-1009', 'C-002', '2026-09-08T14:00:00', 'delivered',  '2026-09-11T10:50:00', '2026-09-12', 'TX', 'summit', 0.00),  -- jewelry $640
 ('JP-1010', 'C-001', '2026-09-14T09:45:00', 'shipped',    NULL,                  '2026-09-18', 'TX', 'basic',  9.95),  -- late, not delivered
 ('JP-1011', 'C-004', '2026-09-16T17:25:00', 'delivered',  '2026-09-20T09:35:00', '2026-09-21', 'TX', 'basic',  9.95);  -- customer with 4 recent returns

INSERT INTO items VALUES
 -- item_id, order_id, name, category, price_paid, tax, is_set, tags, final_sale_flag, final_sale_on_confirmation, is_oversized
 ('IT-1001', 'JP-1001', 'Trailhead Shell Jacket',       'apparel_footwear',    120.00,  9.60, 0, '',          0, 0, 0),
 ('IT-1002', 'JP-1002', 'Ridgeline Over-Ear Headphones','electronics',         200.00, 17.00, 0, '',          0, 0, 0),
 ('IT-1003', 'JP-1003', 'Pine Bookshelf, 5 Shelf',      'furniture_oversized', 180.00, 14.40, 0, '',          0, 0, 1),
 ('IT-1004', 'JP-1004', 'Enamel Dinnerware Set',        'home_goods',           55.00,  3.30, 1, '',          0, 0, 0),
 ('IT-1005', 'JP-1005', 'Mountain Gourmet Gift Basket', 'perishables',          12.00,  0.96, 0, '',          0, 0, 0),
 ('IT-1006', 'JP-1006', 'Summit 3-Person Tent',         'outdoor_gear',        320.00, 25.60, 0, '',          0, 0, 0),
 ('IT-1007', 'JP-1007', 'Fleece Pullover',              'apparel_footwear',     75.00,  6.00, 0, '',          0, 0, 0),
 ('IT-1008', 'JP-1008', 'Summer Clearance Rain Jacket', 'apparel_footwear',     90.00,  7.99, 0, 'clearance', 1, 0, 0),
 ('IT-1009', 'JP-1009', 'Silver Pendant Necklace',      'jewelry',             640.00, 51.20, 0, '',          0, 0, 0),
 ('IT-1010', 'JP-1010', 'Brass Table Lamp',             'home_goods',          110.00,  8.80, 0, '',          0, 0, 0),
 ('IT-1011', 'JP-1011', 'Merino Base Layer',            'apparel_footwear',     60.00,  4.80, 0, '',          0, 0, 0);
