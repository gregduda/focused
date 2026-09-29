# Design decisions log

Newest entries at the bottom. Format: what we decided, alternatives, why.

## D-001 Answer key stays at repo root, outside the indexed corpus
- Decision: `GROUND_TRUTH.md` lives at the repo root; only `refund_policies/**/*.md` (minus its README) is indexable.
- Alternatives: move into a gitignored/private folder; rejected for now since it is fine to ship in the repo.
- Why: hard rule that the answer key is never retrieved. Enforced by a test (to be written in scaffolding).

## D-002 Keep corpus path `refund_policies/` (not `docs/`)
- The corpus README and answer key say `docs/`. Renaming would churn the given files; the loader takes the path as config.

## D-003 Agent gets `today` as an input
- Rules depend on the current date and evals must be reproducible, so no system-clock calls in agent code.

## D-004 v1 has no metadata filtering; v2 adds it later
- The stale docs (ARC-01/02, SUP-02, MKT-01) are the intended v1 failure to measure. Filtering is added only on user instruction.

## D-005 Single-turn agent; verification attempts are an input
- Decision: each run is one customer message. The request carries `failed_verification_attempts` (int) so the OPS-02 "two failed attempts -> escalate" rule is testable without conversation state.
- Alternative: a multi-turn conversation loop with a checkpointer. Rejected: more moving parts and harder to make eval cases reproducible.
- Cost: cannot evaluate real back-and-forth clarification. Listed as a known limitation.

## D-006 Three decision labels only; non-decisions map to ESCALATE
- Decision: decision is APPROVE, DENY or ESCALATE. Cases that need a clarifying question, a 48-hour wait, or a failed verification are ESCALATE, with the customer message saying what is needed.
- Alternative: add NEEDS_INFO. Rejected for simplicity and to match the answer key's labels.
- Cost: ESCALATE mixes "a human must decide" with "we need more info", which inflates escalation counts. Consider a separate `escalation_type` field for slicing, not for scoring.

## D-007 Keep-it refund limit changed from $75 to $15 (user decision)
- Edited the corpus (POL-11, POL-04, CAT-05, OPS-01) and GROUND_TRUTH.md to match. Freight pickup $75 is unrelated and unchanged.
- GT rows changed: E1 (mug $28 now ESCALATE; $12 mug is the approve path), E2 note, E4 (basket now $12.00/$0.96 -> $12.96; $45 case now ESCALATE), section 1.3, retrieval Q, assumptions.
- Why: a lower limit makes the escalation boundary reachable with ordinary cheap items and makes keep-it cases more interesting to evaluate.
- Note for README: the corpus was modified from its generated original; say so.

## D-008 Defaults for open questions 6, 7, 8
- Abuse flag (OPS-03) escalates even when the item is clearly ineligible. Reason: OPS-03 says escalate "instead of approving or denying"; a human decides.
- The $250 limit applies to the net refund (after fees, before any store-credit bonus). The $500 jewelry rule uses price paid, as CAT-06 says.
- Never disclose the $250, $500, or abuse thresholds. Windows, fees, and the $15 keep-it limit (customer-facing POL-11) may be stated.

## D-009 OpenAI as the LLM provider
- Decision: agent, judge, and embeddings use OpenAI via `langchain-openai`; model names come from env/config.
- Why: user's available key. LangGraph/LangSmith are provider-agnostic, so nothing else changes.
- Judge uses a different model than the agent to reduce self-preference bias.
