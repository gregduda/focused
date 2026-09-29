---
doc_id: OPS-03
title: Return Abuse and Fraud Signals
doc_type: agent_ops
status: active
authority: authoritative
effective_date: 2026-01-01
last_reviewed: 2026-09-10
audience: support agents, including the AI support agent
---
# Return Abuse and Fraud Signals

## Thresholds
Escalate to the loss prevention queue instead of approving or denying when either is true for the customer's last 60 days:
- **4 or more** returns (`returns_last_60d`), or
- **$1,000 or more** refunded (`refunded_last_60d`).

A second keep-it refund request within 90 days of an earlier one is also escalated (POL-11).

## Common patterns
Wearing an item and returning it, returning empty boxes, returning items that were not sold by J&P, and repeated claims that packages never arrived.

## How to handle it
- Never accuse the customer.
- Never mention the flag, the thresholds, or the fraud process.
- Use neutral wording, for example: "I'm passing this to a specialist who will follow up."
- Do not approve, deny, or issue refunds while it is pending.

## Why escalate rather than deny
A high return count alone is not proof of abuse. A human decides.
