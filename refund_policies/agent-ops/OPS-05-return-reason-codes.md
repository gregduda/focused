---
doc_id: OPS-05
title: Return Reason Codes
doc_type: agent_ops
status: active
authority: authoritative
effective_date: 2026-01-01
last_reviewed: 2026-08-25
audience: support agents, including the AI support agent
---
# Return Reason Codes

Every return or refund is logged with one reason code.

## Our-error reasons
These waive the label fee, restocking fees, and freight pickup fee, and they can qualify for an outbound shipping refund (POL-08).
- `DEFECTIVE`: the item does not work or has a manufacturing flaw.
- `DAMAGED_IN_TRANSIT`: the item arrived damaged.
- `WRONG_ITEM_SENT`: the customer received a different item than ordered.
- `NOT_AS_DESCRIBED`: the item differs materially from the product page.

## Customer-initiated reasons
These carry the normal fees.
- `CHANGED_MIND`
- `WRONG_SIZE_FIT`
- `ORDERED_BY_MISTAKE`
- `FOUND_CHEAPER`
- `GIFT_UNWANTED`
- `LATE_DELIVERY`: a late delivery does not waive fees or extend the window, because the window starts at delivery.

## Choosing the code
Use the reason the customer gives. If the customer gives an our-error reason for something that sounds like misuse or a change of mind, do not approve it as our-error without more information. Ask a clarifying question, or escalate if unclear.
