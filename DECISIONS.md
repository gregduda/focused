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
