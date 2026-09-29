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

## D-010 Python 3.14 with requirements.txt
- Decision: use the system Python 3.14 and a `requirements.txt` (no pyproject.toml), per user preference.
- Checked: langchain 1.4.3, langgraph, langchain-openai, langsmith 0.14.1 install and import on 3.14 (one DeprecationWarning only).
- Risk: some transitive dependency (e.g. a vector store) may lack 3.14 wheels; pin versions in requirements.txt once chosen and fall back to 3.12 if one breaks.

## D-011 gpt-5.4-nano for both agent and judge
- Decision: one model, `gpt-5.4-nano`, for the agent and the LLM judge (user choice). Model name is config, so it can change per role later.
- Cost: the judge shares the agent's blind spots and may favor its own style (self-preference bias); a nano-size judge is also weaker at subtle judgments.
- Mitigations: deterministic checks decide decision/amount/date/escalation/disclosure; the judge only grades tone and invented-policy; calibrate the judge against a small hand-labeled set and report agreement; state this limitation in the README.
- Embedding model not chosen yet.

## D-012 Model name comes from `.env` (`OPENAI_MODEL`)
- Decision: a single `OPENAI_MODEL` entry (value `gpt-5.4-nano`) in `.env` and `env.example`; code never hard-codes a model name.
- One variable serves both agent and judge for now. If we later want a different judge, add `JUDGE_MODEL` that falls back to `OPENAI_MODEL`.

## D-013 Embedding model: text-embedding-3-small (default pick)
- Decision: `OPENAI_EMBEDDING_MODEL=text-embedding-3-small` in `.env` and `env.example`. Verified with a live call (1536 dimensions).
- Why: cheap, widely used, plenty for ~51 short docs. Retrieval quality is not the thing we are tuning; the v1-to-v2 change is metadata filtering.
- Note: changing the embedding model requires rebuilding the index.

## D-014 Pinned requirements.txt, kept current
- Decision: `requirements.txt` with exact versions (langchain, langchain-openai, langgraph, langsmith, python-dotenv, PyYAML, pytest), taken from a working install on Python 3.14. Updated whenever a new library is imported.
- Why: reproducible quickstart for reviewers. No vector store added yet; it will be added when we choose one.

## D-015 Indexing: chunk by `##` section into a local Chroma DB
- Code: `src/rag/embed_sources.py` (run `python -m src.rag.embed_sources` from the repo root). Config in `.env`: `POLICY_DOCS_DIR`, `CHROMA_DIR`, `CHROMA_COLLECTION` (plus the embedding model).
- Chunking: one chunk per `##` section, prefixed with "Title (DOC-ID)". Text between the H1 and the first `##` becomes an "Overview" chunk (needed: e.g. CAT-04's definition of oversized lives there). Result: 244 chunks from 51 docs.
- Metadata stored per chunk: doc_id, title, doc_type, status, authority, category, state, section, source path. v1 ignores them at query time; v2 will filter on them.
- Rebuild from scratch on every run (`reset_collection`), ids `DOC-ID::n`, so removed or edited docs never linger.
- Leak guard: only `POLICY_DOCS_DIR` is read, the corpus README is skipped, and the script asserts no GROUND_TRUTH file is in the list. A proper pytest for this is still to be written.
- Smoke check: "restocking fee for opened electronics shipped to California" returns ST-CA, CAT-02, POL-06, then SUP-01 (a non-authoritative macro), so the distractor problem shows up even in v1 retrieval.
- Chroma DB lives in `chroma_db/` (gitignored). Added `chromadb` and `langchain-chroma` to requirements.txt; installed on 3.14 without issues. Project venv is `.venv/` (gitignored).

## D-016 Chunk visualization script
- Code: `src/rag/plot_chunks.py` (`python -m src.rag.plot_chunks`) writes `viz/chunks.html` (gitignored, `CHROMA_CHUNK_PLOT_DIR` in `.env`). Reads stored vectors from Chroma, so no embedding API calls.
- Projection: t-SNE with cosine distance, fixed seed (sklearn, no extra install risk on 3.14; UMAP skipped because its numba dependency is a risk). Dropdown recolors by authority, status, doc_type, category, or state; hover shows doc, section, preview.
- Limits: 2D projections distort distances. This is an exploration aid for the README/interview, not an eval.
- Added numpy, scikit-learn, plotly to requirements.txt.

## D-017 No code-level guard or test for the answer key (supersedes the guard in D-001/D-015)
- Decision: `GROUND_TRUTH.md` lives outside `refund_policies/`, the only directory the indexer reads. The assert in `embed_sources.py` was removed and no leak-guard test will be written.
- Why: user decision; the separation is structural. The indexer only reads `POLICY_DOCS_DIR`, so the file can't be indexed unless someone moves it in there.
- Residual risk: pointing `POLICY_DOCS_DIR` at the repo root, or moving the file into `refund_policies/`, would silently index it. Also, the index still has to be rebuilt after any corpus edit.

## D-018 Retriever added; embedding model is the langchain default (supersedes D-013)
- Code: `src/rag/chunk_retriever.py` (`retrieve(query, k=RETRIEVER_TOP_K)`, no metadata filtering, returns chunks best-first with a `distance`), `tests/rag/chunk_retriever_test.py` (`pytest tests/rag -s` prints the retrieved chunks), `pytest.ini` (`pythonpath = .`). `RETRIEVER_TOP_K=4` in `.env`.
- The user changed `embed_sources.py` to `OpenAIEmbeddings()` with no model and removed `OPENAI_EMBEDDING_MODEL` from `.env`. langchain's default is `text-embedding-ada-002`. The index and the retriever must use the same model.
- Incident: I re-added `text-embedding-3-small` to the retriever/.env without noticing the change. Index and queries were in different vector spaces (cosine ~0.07 between a chunk and its own re-embedded text), so retrieval returned near-random chunks (distances ~1.8-1.9). Fixed by making the retriever use `OpenAIEmbeddings()` too. Lesson: a model mismatch fails silently, with no error. Any change to the embedding model means re-running `python -m src.rag.embed_sources`.
- Risk: the model is now implicit. If langchain changes its default, index and queries would drift apart again. An explicit env var shared by both files would be safer.
- First v1 retrieval observations (real failures for the before/after story): "How long do I have to return a bookshelf?" ranks SUP-02 (stale, says furniture 60 days), POL-01, ARC-01, SUP-01 and does not retrieve CAT-04 in the top 4. "Holiday return deadline for electronics" ranks ARC-02 (unapproved draft, Feb 15) first. "website says love it or send it back anytime" retrieves MKT-01 first.

## D-019 Local embeddings: Chroma default all-MiniLM-L6-v2 (supersedes D-013 and D-018)
- Decision (user): no `embedding_function` is passed in `embed_sources.py` or `chunk_retriever.py`, so Chroma uses its built-in local all-MiniLM-L6-v2 (384 dimensions, ONNX, downloaded once to `~/.cache/chroma`, about 79 MB). No `OPENAI_EMBEDDING_MODEL` in `.env`.
- Benefits: no API cost or latency for embedding, tests run offline after the first download, nothing implicit in langchain's defaults. Chroma applies the same function at index and query time, which removes the mismatch failure from D-018 as long as neither file passes its own function.
- Costs: MiniLM is smaller than OpenAI embeddings and truncates input at about 256 word pieces (our chunks are short, so this is fine). The first run needs internet for the model download. Distances are on a different scale than before (`dist` up to ~1.3), so do not compare distance numbers across models.
- Index rebuilt: 244 chunks, 51 docs. Retrieval quality is reasonable: California restocking returns ST-CA first; distractors still appear (bookshelf returns SUP-02, SUP-01, ARC-01, POL-01 and misses CAT-04 entirely; holiday electronics ranks the ARC-02 draft first; doorbuster query pulls ARC-02 4th). These are the v1 failures to measure.

## D-020 No identity verification step (user decision; revises D-005)
- Decision: the agent takes `order_id`, the customer message, and `today`. It loads the order by id with no email or gift-code check and no `failed_verification_attempts` input. OPS-02's verification rules and the OPS-01 "identity cannot be verified" escalation are out of scope.
- Why: extra complexity that does not serve the assignment's evaluation story.
- Consequences: (1) eval case G4 (wrong email twice) is dropped; (2) see D-023 for gift orders; (3) the agent will act on any order id it is given, which must be stated in the README as a limitation (a production agent needs authentication upstream); (4) OPS-02's PII rules still apply to messages: never repeat a pasted card number, mask emails, do not repeat the full address (case G5 stays).
- The "don't reveal whether an order exists" behavior is not needed, since there is no pre-verification state.

## D-021 Calculators and actions are LLM tool calls; order load and retrieval are fixed steps
- Decision (user-confirmed): the LLM gets a small set of deterministic calculators (return deadline, fees, refund amount) and action tools (create RMA, keep-it refund, cancel order, exchange, escalate) via standard LangChain/LangGraph tool calling. Loading the order and retrieving policy chunks are fixed steps before the LLM, not tools.
- Calculators are parameterized: the LLM reads values (window days, fee percentages) from the retrieved docs and passes them as arguments. They contain no policy. Retrieval quality therefore affects the answer, which is what the evals measure.
- Why: arithmetic and dates stay in code (hard rule 3), every call is visible in the LangSmith trace, and retrieval stays load-bearing.
- Risks: the LLM may skip a calculator or pass the wrong argument (for example 45 days instead of 30). This is testable with tool-call/trajectory evals. Keep the tool set small.
- Alternative not taken: hard-coding the policy in the calculators. More accurate, but retrieval becomes decorative and the eval loses its main lever.

## D-022 SQLite read-only order database; actions in memory (user decision)
- Decision: mock orders and customers live in a SQLite file (`orders.db`; tables `customers`, `orders`, `items`) opened read-only. The file is created from `schema.sql` and `seed.sql`; there is no Python build script or second copy of the data (user pointed this out). The oracle reads the rows and computes expected values. Agent actions are recorded in an in-memory list per run and are never persisted.
- Why (user): a database is easier to reason about than JSON files. SQLite needs no server and ships with Python.
- Conventions: money in integer cents, dates as ISO text, booleans 0/1.
- Tradeoff: eval cases refer to orders by id, so seed rows and case entries must be kept consistent, and dates are absolute (computed by hand from each case's `today`, then verified by a check script). Alternative rejected: per-case order records embedded in the dataset.
- Supersedes the "in-memory store seeded from JSON" idea in `design/mock-data.md`.

## D-023 Gift returns are out of scope (user decision)
- Decision: no gift-recipient vs buyer distinction. No `is_gift_order`, `gift_receipt_code`, or `requester_role` fields; no gift-return eval cases (GT B21, F1); the agent has no gift-return logic.
- Why: with identity verification removed (D-020) the agent cannot tell who is asking, and the user does not want the extra rules and examples.
- Not affected: the POL-09 "free gift with purchase" rule (a promotion, unrelated to gift orders) and gift cards (CAT-08).
- Corpus left as is: POL-12 stays in `refund_policies/` and in the index, so a gift-related question can still retrieve it, and POL-04 and OPS-02 still mention gift returns. If a gift question shows up, the agent should not apply POL-12 as if it were in scope; decide in the dataset whether that is a case at all. Removing or editing POL-12 in the corpus was not requested.

## D-024 Timestamps for 48-hour rules, single-item orders, unknown order id escalates (user decisions)
- Timestamps: `AgentRequest.now` (optional datetime) and `Order.delivered_at` (optional datetime), used only by perishables (CAT-05) and delivered-not-received (POL-11) cases. `today` is still always passed; the loader checks that `now.date() == today` and `delivered_at.date() == delivered_date`, so the two cannot disagree. Still no system clock in the agent.
- Single-item orders: each order has exactly one item. Removed `promo` and `list_price` from the schema. The `items` table stays for later extension.
- Dropped answer-key cases: B17, B18, B19 (need two items). Kept: B20 (free gift), B15 (whole-order shipping refund, trivially true for one item), C14 (a set is one item).
- Unknown order id: `get_order` returns `None`; the agent ESCALATEs saying the order could not be found (fits D-006).
- Consequence for the README: multi-item orders, promo proration, and spend-threshold rules (POL-09) are listed as untested.

## D-025 Mock data implemented
- Files: `data/schema.sql`, `data/seed.sql` (4 customers, 11 demo orders, one item each), `src/data/models.py` (Pydantic), `src/data/store.py` (read-only `OrderStore` with in-memory `actions`), `tests/data/store_test.py`. `ORDERS_DB_PATH=data/orders.db` in `.env`; the generated `data/orders.db` is gitignored.
- Create the database: `sqlite3 data/orders.db < data/schema.sql && sqlite3 data/orders.db < data/seed.sql` (schema.sql drops and recreates the tables, so rerunning is safe).
- Enforced by the schema and models: exactly one item per order, delivered orders have a delivered date and others do not, tiers and categories limited to the allowed values, `delivered_at` on `delivered_date`, `now` on `today`.
- The 11 seed orders are demo scenarios written for this project, not copies of answer-key rows. Eval-case orders will be added to `seed.sql` when the dataset is built.
- Added pydantic to requirements.txt.

## D-026 Date-times for order and delivery; money stored as floats (user decisions; revises D-024 and D-025)
- `order_date` and `delivered_date` are now ISO date-times (naive, read as US Pacific per POL-02). The separate `delivered_at` column and its consistency check were removed. The 48-hour rules use `delivered_date` and the request's `now`. Window logic counts calendar days from `delivered_date.date()`.
- Money columns are REAL dollars (120.00, 9.60, 8.54), not integer cents. To avoid float error, `OrderStore` rounds each value to two decimals and converts it to `Decimal`; models and calculators only see `Decimal`.
- Risk: floats in the database can carry representation error (for example 0.1 + 0.2). Rounding at read time removes it as long as amounts have at most two decimals, which the seed data respects. Never do arithmetic on the raw database values.
- `estimated_delivery_date` and `last_keep_it_refund_date` stay date-only. The database was rebuilt and all tests pass.

## D-027 Dropped `free_gift_value` from orders (user decision)
- Removed from the schema, seed, models, store, and design doc. Added `first_name` and `last_name` to customers (for greeting the customer).
- Why: it served one rule (POL-09 free gift deducted if not returned) and one answer-key case (B20). Not worth a field and extra model logic.
- Consequence: the POL-09 free-gift rule joins the untested rules (with spend-threshold and proration). List them in the README limitations. Answer-key case B20 is dropped; D-024's "Kept: B20" no longer holds.
- Kept: `estimated_delivery_date` (POL-11 lost-package rule) and `outbound_shipping_paid` (POL-08/POL-14 shipping refunds).

## D-028 LangSmith tracing on; four parameterized calculator tools
- Tracing: `LANGSMITH_TRACING=true` and `LANGSMITH_PROJECT=refund-agent` in `.env` and `env.example`. Verified: a traced call showed up as a root run in the `refund-agent` project. Nodes that are plain Python (order load, retriever) still need `@traceable` to appear as spans.
- Calculators (`src/tools/calculators.py`, tests in `tests/tools`), plain functions plus `CALCULATOR_TOOLS`:
  1. `compute_deadline(start, windows, today)`: takes every candidate window (days from start, or a fixed date), applies the LATEST (windows never stack, POL-07), and says whether today is on or before it (inclusive), with days remaining. Also serves other clocks, such as the 7-day damage report or the 90-day keep-it rule.
  2. `compute_refund(price_paid, tax, restocking_pct, label_fee, pickup_fee, outbound_shipping_refund, store_credit_bonus_pct)`: POL-08 formula with a fee breakdown. The LLM decides which fees apply and passes 0 for waived or inapplicable ones.
  3. `check_claim_window(start_date, today, wait_business_days, max_calendar_days)`: lost-package rule (POL-11). Business days are Monday to Friday with no holiday calendar.
  4. `check_elapsed_hours(start, now, limit_hours)`: the 48-hour rules; returns both `within_limit` (report within 48h) and `limit_reached` (wait 48h first).
- Design points: dates in as ISO strings; money in as numbers, computed as Decimal, out as two-decimal strings; percentage fees and the store-credit bonus round half up (the bonus rounding is our assumption, the corpus is silent); the tools raise ValueError on bad input and do not floor a negative refund, they flag `refund_is_negative`. None of them contains policy numbers.
- Not built: threshold checks ($250 limit, $500 jewelry, $15 keep-it, abuse counts). These depend on the open decision about where authority checks live. A `check_limit(amount, limit, inclusive)` tool is the obvious fifth calculator if we keep them in the LLM step.
