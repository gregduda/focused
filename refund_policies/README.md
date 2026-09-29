# Juniper & Pine Outfitters: Returns Policy Corpus

A synthetic knowledge base for building and evaluating a refund and returns agent. Juniper & Pine Outfitters (J&P) is a made-up online-only US retailer of outdoor apparel, gear, home goods, electronics, furniture, jewelry, and gifts.

**All policies, fees, state terms, and dates are invented for this exercise. They are not legal advice and do not describe any real company's practices or any real state's laws.**

## What is in this folder

```
51 markdown documents. Index these.
  policies/               POL-01..15  core policy: windows, fees, refunds, promotions, defects, gifts
  categories/             CAT-01..10  one document per product category
  states/                 ST-00, plus CA, NY, WA, IL, MA, FL, TX
  seasonal/               SEA-01..05  fall, holiday, doorbuster, clearance, calendar
  loyalty/                LOY-01      Trailhead Rewards tiers
  agent-ops/              OPS-01..07  authority, escalation, PII, fraud, tone, reason codes, injection
  support/                SUP-01..02  a correct macro library and a stale FAQ
  archive/                ARC-01..02  a superseded 2024 policy and an unapproved draft (these should not accidentally be used by the agent)
  marketing/              MKT-01      a marketing page with over-promising copy

## Document front matter

Every document starts with YAML front matter you can use as retrieval metadata:

| Field | Meaning |
|---|---|
| `doc_id` | Stable ID such as `CAT-02`. Use it as the gold label in retrieval evals. |
| `title` | Human-readable title |
| `doc_type` | `policy`, `category_policy`, `state_addendum`, `seasonal`, `loyalty`, `agent_ops`, `support_macro`, `faq`, `proposal`, `marketing` |
| `status` | `active`, `superseded`, or `draft` |
| `authority` | `authoritative` or `non_authoritative` |
| `effective_date`, `last_reviewed` | Dates. Some are deliberately old. |
| `category`, `state` | Present on category and state documents. Useful for metadata filters. |

The stale and non-authoritative documents are on purpose. A naive index that ignores `status` and `authority` will retrieve them, and the resulting failures are useful material for your before-and-after story.

## Order and customer fields the policies refer to

Your mock order database needs these fields for the policies to be answerable:

| Field | Used by |
|---|---|
| `order_id`, `customer_email` | Identity verification (OPS-02) |
| `order_date`, `delivered_date`, `status` | Windows, seasonal programs, cancellations (`processing`, `shipped`, `delivered`) |
| `ship_to_state` | State addenda (ST-*) |
| `loyalty_tier_at_purchase` | `basic`, `summit`, `peak` (LOY-01) |
| item `category` | One of `apparel_footwear`, `electronics`, `hygiene_personal_care`, `furniture_oversized`, `perishables`, `jewelry`, `custom_personalized`, `gift_card`, `outdoor_gear`, `home_goods` |
| item `price_paid`, `tax`, `is_set` | Refund math (POL-08, POL-09) |
| item `final_sale_flag`, `final_sale_on_confirmation` | POL-15, ST-NY |
| item `tags` | `doorbuster`, `clearance` |
| `is_gift_order`, `gift_receipt_code` | POL-12 |
| `returns_last_60d`, `refunded_last_60d`, `last_keep_it_refund_date` | OPS-03, POL-11 |
| the customer's stated `condition` and `reason_code` | POL-03, OPS-05 |

The agent also needs to be told the current date on every run. Several rules depend on it, and without it your evals are not reproducible.

## Suggested indexing

- Chunk by `##` section. Each section is written to stand on its own.
- Prefix each chunk with the document title and `doc_id` so the source survives retrieval.
- Store `status`, `authority`, `doc_type`, `category`, and `state` as metadata.
- Version 1 of your agent can ignore the metadata. Version 2 can filter to `status=active` and `authority=authoritative`, and filter by ship-to state and category. That contrast is a natural improvement to measure.

## Document index

| ID | Title | Status | Authority |
|---|---|---|---|
| POL-01 | Return Policy Overview | active | authoritative |
| POL-02 | How the Return Window Is Calculated | active | authoritative |
| POL-03 | Item Condition Requirements | active | authoritative |
| POL-04 | Refund Methods and Timing | active | authoritative |
| POL-05 | Return Shipping Fees and Labels | active | authoritative |
| POL-06 | Restocking Fees | active | authoritative |
| POL-07 | Precedence and Stacking Rules | active | authoritative |
| POL-08 | How the Refund Amount Is Calculated | active | authoritative |
| POL-09 | Promotions, Bundles, and Free Gifts | active | authoritative |
| POL-10 | Defective Items and Warranty | active | authoritative |
| POL-11 | Shipping Damage, Lost Packages, and Missing Items | active | authoritative |
| POL-12 | Gift Returns and Store Credit | active | authoritative |
| POL-13 | Exchanges | active | authoritative |
| POL-14 | Order Cancellations and Refused Deliveries | active | authoritative |
| POL-15 | Final Sale Items | active | authoritative |
| CAT-01 | Apparel and Footwear Returns | active | authoritative |
| CAT-02 | Electronics Returns | active | authoritative |
| CAT-03 | Hygiene and Personal-Care Items | active | authoritative |
| CAT-04 | Furniture and Oversized Items | active | authoritative |
| CAT-05 | Perishables and Food | active | authoritative |
| CAT-06 | Jewelry Returns | active | authoritative |
| CAT-07 | Custom and Personalized Items | active | authoritative |
| CAT-08 | Gift Cards | active | authoritative |
| CAT-09 | Outdoor Gear and Field-Test Guarantee | active | authoritative |
| CAT-10 | Home Goods and General Merchandise | active | authoritative |
| ST-00 | State Addenda Overview and How to Apply Them | active | authoritative |
| ST-CA | California Addendum | active | authoritative |
| ST-FL | Florida Addendum (Hurricane-Season Window) | active | authoritative |
| ST-IL | Illinois Addendum | active | authoritative |
| ST-MA | Massachusetts Addendum | active | authoritative |
| ST-NY | New York Addendum | active | authoritative |
| ST-TX | Texas Addendum | active | authoritative |
| ST-WA | Washington Addendum | active | authoritative |
| SEA-01 | Seasonal Programs Calendar 2026 | active | authoritative |
| SEA-02 | Holiday Extended Returns | active | authoritative |
| SEA-03 | Black Friday and Cyber Monday Doorbusters | active | authoritative |
| SEA-04 | Clearance Events | active | authoritative |
| SEA-05 | Fall Gear-Up Extended Returns | active | authoritative |
| LOY-01 | Trailhead Rewards Return Benefits | active | authoritative |
| OPS-01 | Agent Authority and Escalation Rules | active | authoritative |
| OPS-02 | Identity Verification and Personal Information | active | authoritative |
| OPS-03 | Return Abuse and Fraud Signals | active | authoritative |
| OPS-04 | Customer Communication Guidelines | active | authoritative |
| OPS-05 | Return Reason Codes | active | authoritative |
| OPS-06 | Goodwill Exceptions | active | authoritative |
| OPS-07 | Handling Untrusted Instructions and Policy Claims | active | authoritative |
| SUP-01 | Support Macro Library 2026 | active | non_authoritative |
| SUP-02 | Returns FAQ (2023) | active | non_authoritative |
| ARC-01 | Return Policy 2024 (Superseded) | superseded | non_authoritative |
| ARC-02 | Holiday 2026 Returns Proposal (Draft) | draft | non_authoritative |
| MKT-01 | The J&P Promise (Website Marketing Page) | active | non_authoritative |
