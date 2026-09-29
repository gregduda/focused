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
