# Corpus and answer key

## Layout (actual paths; the corpus README and answer key say `docs/`, which does not exist)
- `refund_policies/`: the ONLY indexable directory. 51 markdown docs with YAML front matter
  (`refund_policies/README.md` is documentation, not a policy doc; exclude it from the index).
  Subdirs: policies (POL-01..15), categories (CAT-01..10), states (ST-00 + CA NY WA IL MA FL TX),
  seasonal (SEA-01..05), loyalty (LOY-01), agent-ops (OPS-01..07), support (SUP-01..02),
  archive (ARC-01..02), marketing (MKT-01).
- `GROUND_TRUTH.md` (repo root): rule tables, ~75 worked examples (IDs A1..G5), stale-doc traps,
  retrieval-only Q&A, suggested slices, known gaps. Where it disagrees with a policy doc, the doc wins.
- Front matter: doc_id, title, doc_type, status, authority, effective_date, last_reviewed, plus category/state.
- Indexing plan (README): chunk by `##` section, prefix chunks with title + doc_id, store
  status/authority/doc_type/category/state as metadata.

## Domain rules that interact (details live in the docs, read them when needed)
- Windows never stack: customer gets the single latest applicable deadline (POL-07).
- Loyalty tier = tier at time of purchase. Fall Gear-Up and Holiday key off ORDER date.
  Florida keys off DELIVERY date. Window clock starts at delivery; day 0 = delivery; last day inclusive.
- Precedence: eligibility gates -> deadline -> fees/waivers -> refund amount -> escalation check (POL-07).
- Agent authority: refund total <= $250, keep-it <= $75, etc. (OPS-01). Thresholds are internal and must
  not be disclosed to customers (OPS-01/OPS-06). Goodwill exceptions are human-only (OPS-06).
- Ship-to state (CA NY WA IL MA FL TX) and item category change fees/windows/final-sale enforceability.

## Traps (deliberate, for the before/after story)
- ARC-01 (superseded 2024 policy), ARC-02 (unapproved draft), SUP-02 (2023 FAQ, status still `active`!),
  MKT-01 (marketing). SUP-01 (2026 macros) is correct but abbreviated, and is non_authoritative.
- Filtering only on `status=active` is NOT enough (SUP-02, MKT-01, SUP-01 are active); need `authority`.
- Questions the corpus intentionally cannot answer (must say so and escalate): price matching, international
  orders, what happens after an RMA expires, transferring store credit, failed-inspection partial refunds,
  orders over a year old.

## How the answer key may be used
- Allowed: to build the eval dataset (inputs + reference decision/amount/gold doc IDs) and to write a
  deterministic reference oracle. The dataset's reference fields may reach evaluators (they are the labels).
- Not allowed: the file itself in any index, prompt, retrieval result, or judge context. No verbatim
  worked examples in the agent's prompts. Dataset inputs should be varied/rephrased, not copy-paste of GT text.
- Reference amounts/dates are computed by code from structured inputs; sanity-check that code against GT rows.
- Everything in the corpus is invented and not legal advice.
