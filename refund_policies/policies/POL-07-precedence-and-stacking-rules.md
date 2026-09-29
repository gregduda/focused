---
doc_id: POL-07
title: Precedence and Stacking Rules
doc_type: policy
status: active
authority: authoritative
effective_date: 2026-01-01
last_reviewed: 2026-09-01
applies_to: all returns
---
# Precedence and Stacking Rules

## Order of evaluation
Support agents evaluate a return in this order:
1. **Eligibility gates:** Is the item final sale (POL-15)? Does the category exclude it (CAT documents)? Is the condition acceptable (POL-03)?
2. **Return deadline:** List every window that applies and take the latest. See below.
3. **Fees and waivers:** Apply the lowest applicable fee (POL-05, POL-06, CAT-04).
4. **Refund amount:** Calculate per POL-08.
5. **Escalation check:** See OPS-01 before approving.

## Windows never stack
Return windows and deadlines do not add together. The customer gets whichever single deadline is latest. Examples:
- Summit member (45 days) during Fall Gear-Up (45 days) gets 45 days, not 90.
- A Florida delivery (37 days) for a Summit member (45 days) gets 45 days.
- A holiday order with a January 31 deadline delivered January 20 gets 30 days from delivery (February 19) if that is later.

## Which document wins
- State addenda override the core and category numbers they name. They change nothing else.
- Category documents override core documents when they differ.
- Seasonal and loyalty programs only extend windows or reduce fees. They never remove a category exclusion, such as opened hygiene items or final sale.
- Support macros, FAQs, and marketing pages never override policy documents.
- Documents with status `superseded` or `draft` do not apply to any customer.

## Unresolved conflicts
If two active, authoritative documents still appear to conflict after applying these rules, escalate to a human instead of guessing.
