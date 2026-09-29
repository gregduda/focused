---
doc_id: POL-02
title: How the Return Window Is Calculated
doc_type: policy
status: active
authority: authoritative
effective_date: 2026-01-01
last_reviewed: 2026-08-14
applies_to: all products
---
# How the Return Window Is Calculated

## Which date starts the clock
The window starts on the **delivery date** recorded from the carrier's "delivered" scan (`delivered_date`). It does not start on the order date or the ship date. A late delivery does not extend the window, because the clock only starts once the item arrives.

## Counting days
The day of delivery is day 0. The next calendar day is day 1. The last eligible day is the final day of the window, inclusive. Example: delivered September 5 with a 30-day window means the last eligible day is October 5. The deadline is 11:59 PM Pacific Time on that day.

## What must happen by the deadline
The return must be **initiated** by the deadline, meaning the customer has asked for a return authorization (RMA). Once an RMA is issued, the customer has 14 days to ship the item, even if that shipping date falls after the window deadline.

## Not yet delivered
If an order has not been delivered, no return window has started. For missing packages see POL-11. To cancel an order that has not shipped see POL-14.

## Fixed-date deadlines
Some seasonal programs set a fixed deadline instead of a number of days (see SEA-02). When more than one deadline applies, the customer gets the latest one. Deadlines never add together (see POL-07).
