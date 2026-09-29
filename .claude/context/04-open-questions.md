# Open questions / corpus ambiguities (need a user decision; log the outcome in DECISIONS.md)

## Structural
1. Paths: README and GROUND_TRUTH say `docs/`; the real folder is `refund_policies/` with subfolders. Plan: keep as is.
2. Order fields missing from the README list but needed by rules: outbound shipping paid, item list price (for
   promo/threshold math), promo code details, free-gift value, estimated delivery date (POL-11), delivery-scan
   timestamp, damage/claim report time, item opened/sealed/worn condition, oversized attributes, engraving detail,
   gift-card balance, existing keep-it history. Need a mock-data schema decision.
3. RESOLVED (D-024): add `now` and `delivered_at` timestamps for those cases. Was: hour-level rules (perishables 48h, delivered-not-received 48h, "30 hours after delivery") vs a date-only
   `today` input. Either add a `now` timestamp input or restrict those cases to dates.
4. RESOLVED (D-005, revised by D-020): single-turn; identity verification was dropped so there is no attempts input. Was: multi-turn behavior: OPS-02 "two failed verification attempts" needs state across turns. Single-turn with an
   attempts counter input, or a real conversation loop?
5. RESOLVED (D-006): keep three labels; anything that isn't approve/deny maps to ESCALATE. Was: only three decision labels exist, but some correct behaviors are neither: ask a clarifying question (OPS-05),
   "wait 48 hours" (E7 before the wait), and pre-verification refusals. Add a fourth label or map to ESCALATE?

## Policy conflicts and gaps
6. RESOLVED (D-008): abuse flag escalates even if ineligible. Was: precedence of the abuse flag (OPS-03: escalate "instead of approving or denying") vs a clearly ineligible item
   (OPS-01 "clear denials" need no escalation). Likewise jewelry >= $500 that is outside its window.
7. RESOLVED (D-008, D-024): net refund, bonus excluded; multi-item dropped so mixed cases do not arise. Was: "Refund total > $250": net of fees or gross? Does the 5% store-credit bonus count? Mixed multi-item cases
   (one item approvable, one not) have no rule. GT assumes items are evaluated separately, limit on the sum.
8. RESOLVED (D-008): never disclose $250, $500, abuse thresholds. Was: which thresholds are "internal" (never disclose)? OPS-01 hides $250/$500/abuse thresholds, but the answer key's
   retrieval Q "most the agent can approve?" expects $250. Retrieval eval may pass while the end-to-end agent
   should refuse to say it. Keep-it $15 is in customer-facing POL-11; disclosure unclear.
9. Exception requests: D4 ("make an exception" -> ESCALATE) vs G2 (false policy claim -> DENY). Where is the line
   between pushback and an exception request? G3 ("another agent promised") has no single expected label.
10. G1 injection: "evaluate the underlying request normally" but the underlying request is unspecified.
11. Keep-it $15 test uses price paid; does it include tax? (E1 refund includes tax.)
12. Doorbuster: does the tag alone imply final sale, or only when `final_sale_flag` is set / order date in
    Nov 26-30? Out-of-event tagged items are undefined.
13. CAT-09: Field-Test says reason must be "fit or performance" yet also "the only category where a used item can
    be returned for change of mind." Plain change of mind is borderline.
14. C8: California cash-out of small gift-card balances is a policy right, but OPS-01 lists no agent action for it.
15. Rounding: percent fees round half up (POL-08); store-credit bonus rounding is unspecified (B16 = 127.7325).
16. POL-03 takes the customer's stated condition at face value; the customer's honesty is the control. Note as a
    limitation, not a bug.
17. Several GT rows lack numbers (A12, A15, A16, A17, A14 has two variants); the dataset author must supply inputs.

## Retrieval design risks for v2
18. Category filter conflicts with C5/C6: swimwear and in-ear earbuds need CAT-03 though the catalog category is
    apparel/electronics. State/category filters also can't apply to order-less questions. Prefer including
    CAT-03 and universal docs (POL, OPS, SEA, LOY) always, filtering only ST-* and CAT-* narrowly.
19. Do not filter on `effective_date` vs today: SEA-02/03 and ARC-02 have future effective dates.
20. Eval contamination: dataset built from GT and judged by an LLM from the same family as the agent.
