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

## D-029 Agent state and structured result (`src/agent/state.py`)
- State is a `TypedDict` (LangGraph's standard): `request`, `order`, `customer`, `chunks`, `messages` (LLM and tool conversation, with LangGraph's message reducer), `result`. Nodes return only the keys they change. The store is not in the state (not serializable); nodes and tools receive it through the graph config.
- Retrieved chunks are kept as a small flat `RetrievedChunk` (doc_id, section, status, authority, distance, text) so traces and evals (gold-doc recall, stale-doc-retrieved) can read them directly.
- Result = `AgentDecision` (the schema given to the LLM) + `actions` (copied from the store by code when the run ends, so evals can check what was done). `AgentDecision` fields: decision, reason_code (nine of OPS-05's ten codes, without GIFT_UNWANTED; or null), stated_condition (sealed_unopened, opened_unused, assembled, used_or_worn, not_stated), refund_amount, refund_method, escalation_type, cited_doc_ids, rationale (internal, not shown to the customer), customer_message.
- The LLM states reason_code and stated_condition so evals can check that it read the message correctly (they come from the message, not the database).
- `refund_amount` is a two-decimal STRING, not Decimal. Pydantic's Decimal JSON schema contains a regex pattern; with `gpt-5.4-nano` structured output it ran until the output limit ("max_tokens or model output limit was reached"). With `str` it works. A `refund_decimal` property converts for comparisons. Lesson: test a schema against the real model before building on it.
- No cross-field validators on the LLM schema (for example "ESCALATE needs an escalation_type"): a failing validator would crash the run instead of showing up as an eval failure. These invariants become deterministic eval checks. Also to check: refund_amount equals a value the calculators actually returned (amount provenance).
- Calculators take `today` (and `now`) as arguments, so the LLM copies the date into each call (decided in D-031).

## D-030 Removed GIFT_UNWANTED from the reason codes
- It was in `ReasonCode` only because OPS-05 lists ten codes. Gifts are out of scope (D-023), so it gave the model an unused option. A message about an unwanted gift maps to CHANGED_MIND, which has the same fees.
- Easy to restore: one line in `src/agent/state.py`.

## D-031 The model fills in `today` and `now` in calculator calls (user decision)
- Alternative rejected: inject them from the graph state so the model never sees them. That would remove the chance of a wrong date, but adds wrapper code and hides the date from the trace.
- Consequence: a wrong or hallucinated date in a tool call is a possible failure. Add a deterministic eval check that every calculator call used the request's `today` (and `now`), and count violations per run. This is a good candidate for a trajectory eval and for the interview.

## D-032 Agent graph built (v1)
- Files: `src/agent/graph.py` (wiring and `run_agent`), `nodes.py`, `tools.py` (five action tools plus the calculators as `ALL_TOOLS`), `prompts.py`, `state.py`; tests in `tests/agent/graph_test.py`.
- Flow: `load_order` -> (order missing: `order_not_found` -> END) or `retrieve` -> `agent` <-> `tools` -> `finalize` -> END. A step limit of 20 guards against a runaway tool loop.
- Unknown order id: handled in code (no LLM call): records an `open_escalation` action with type `order_not_found` and a fixed message.
- Retrieval (v1): query is the customer message alone, top k from `RETRIEVER_TOP_K` (4), no metadata filtering. The retriever call is wrapped with `@traceable(run_type="retriever")` so the chunks show up as their own step in LangSmith.
- Prompt: behavior rules only (sources of truth, untrusted message, calculator discipline, one action tool per decision, reply style). It contains no policy text, so retrieval failures cannot be hidden by the prompt. The chunks are shown to the model as `[DOC-ID | section]` plus text, without status or authority (a model that could see them could filter stale docs itself, which is the v2 change).
- The customer's email and last name are not shown to the model; the first name is, for the greeting.
- Action tools validate that the order and item exist, record an `Action` in the store's in-memory list, and move no money. `finalize` makes a second LLM call with structured output (`AgentDecision`) and adds the recorded actions.
- Fix during the build: `OrderStore` now uses `check_same_thread=False` because LangGraph runs tools in worker threads. Safe because the connection is read-only.

### First smoke run (not an eval): jacket, wrong fit, TX, Basic, in window
- Expected: APPROVE, refund $121.65 (120.00 + 9.60 - 7.95 label fee; no shipping refund on a change-of-mind return).
- Actual: APPROVE, refund $139.55. The model passed `label_fee=0` and `outbound_shipping_refund=9.95`.
- Cause in the trace: the message-only query retrieved SUP-02 (swimwear FAQ, stale), CAT-01 Fees, Exchanges, and Condition. CAT-01 says "label fee only (POL-05)" without the amount, and POL-05 and POL-08 were not retrieved. The model then guessed the missing numbers instead of escalating, contrary to the prompt's "if the excerpts do not answer, ESCALATE". Two problems: (1) retrieval misses multi-document facts; (2) the model fills gaps with plausible values.
- Also seen: a malformed cited doc id ("CAT-01 Condition"); `stated_condition` was "not_stated" for "never wore it, tags on" (the enum has no "unworn" value, so this may be a schema gap).
- This is one example, not a measurement. Treat it as a hypothesis for the dataset: multi-document answers fail under v1 retrieval.

## D-033 Split the "store" into `OrderDatabase` and `ActionLog` (user decision)
- Why: "store" was ambiguous (storage or the shop) and the class did two unrelated jobs: read-only order lookups, and holding the in-memory list of actions taken in a run.
- `src/data/order_database.py`: `OrderDatabase` (`get_order`, `get_customer`; read-only SQLite; the old `src/data/store.py` is gone). `src/data/action_log.py`: `ActionLog` (`record`, `actions`; in memory, new for every run).
- Both are passed to the graph through the config as `order_db` and `action_log`. `run_agent(request, order_db=None, action_log=None)` creates fresh ones by default; evals can pass their own to inspect the log afterwards.
- Also renamed the vector-database variables in the retrieval code (`_vector_store`, `vector_store`) for the same reason.
- Earlier entries (D-022 to D-032) still say "store"; read them as `OrderDatabase` plus `ActionLog`.
- Tests: `tests/data/order_database_test.py` and `tests/data/action_log_test.py` (46 tests in total pass, including the end-to-end run).

## D-034 Tracing decorator moved onto `retrieve()`; removed the `_search_policy` wrapper
- The wrapper existed only to give `@traceable` something to decorate. The decorator now sits on `retrieve()` in `src/rag/chunk_retriever.py`, and the retrieve node calls it directly. Any other caller of `retrieve` (for example the retrieval evals) also gets the span.
- Cost: `retrieve` now depends on langsmith, and each retrieval eval call creates a trace span when tracing is on.

## D-035 The graph routes on the agent's decision; actions are recorded by code (user direction; supersedes the action-tool part of D-021 and the `finalize` node of D-032)
- Problem with the first build: the agent node ended in prose, so the decision was only implied (by which action tool it happened to call) and a second LLM call (`finalize`) had to read it back out. The design diagram showed the decision routing the graph; the code did not match.
- Now: the agent's tools are the four calculators plus `submit_decision`, whose arguments are the `AgentDecision` fields (including a new `approved_action`: create_rma, keep_it_refund, cancel_order, create_exchange). Calling it ends the agent's work. `read_decision` validates it; `route_decision` sends APPROVE to `record_approval`, ESCALATE to `record_escalation`, DENY straight to `finish`; `finish` builds the `AgentResult`. `nudge` sends the agent back if it replies without any tool call; an invalid submission is returned to the model with an error. All loops are bounded by the step limit.
- The action tools (`create_rma`, `keep_it_refund`, `cancel_order`, `create_exchange`, `open_escalation`) are gone as LLM tools. The record nodes write the same `Action` records from the decision's fields, so a recorded action always matches the decision. `finalize` and its second model call are gone.
- Benefits: the decision is explicit and routable, one fewer model call per run, and no decision-versus-action mismatch to police.
- Costs and risks: the model can now leave `approved_action` empty on an APPROVE (nothing is recorded; an eval must flag it) and can mislabel it. We lose the trajectory check "did the model call the right action tool"; the check becomes "does the decision's approved_action fit the case". `decision`/`approved_action` consistency is checked by evals, not by schema validators (D-029).
- Files: `src/agent/{state,tools,prompts,nodes,graph}.py`, `tests/agent/graph_test.py` (57 tests pass, including one live run). The first live run still gave the v1 wrong answer on the jacket case ($139.55 instead of $121.65, and it cited SUP-02), confirming the failure comes from retrieval and the model guessing, not from the graph shape.

## D-036 A `decide` step (structured output) replaces `submit_decision`, `nudge`, and `read_decision` (user decision; supersedes those parts of D-035)
- Graph now: `load_order` -> (`order_not_found` | `retrieve` -> `agent` <-> `tools` -> `decide` -> route on the label -> `record_approval` / `record_escalation` / `finish`) -> `finish`.
- The `agent` node only gathers facts: it binds the four calculators and stops calling tools when it has what it needs. `decide` is a second model call using `with_structured_output(AgentDecision)`, so the decision is always schema-valid. Routing is on `decision.decision`; the record nodes and `finish` are unchanged (actions are still recorded by code, D-035).
- Removed: the `submit_decision` tool (and `src/agent/tools.py`), the `nudge` node, the `read_decision` node with its retry loop, and the "model did not submit properly" failure class. `route_after_agent` is now a two-way choice (tools or decide).
- Cost: one more model call per run, re-sending the whole prompt (roughly a third more tokens), and the agent's closing prose is mostly discarded. Risk: the analysis and the decision could disagree; `decide` sees the calculator results and is told to copy amounts from them. An eval check should compare the decision's refund amount against the calculator results in the trajectory.
- Observed in the first live run: despite the prompt asking for a brief analysis, the agent's closing message was written as a customer reply ("Hi Alex..."), so the model does not fully follow that instruction. It is harmless (`decide` writes the real reply) but wasteful. The run still produced the known v1 error ($139.55 instead of $121.65), so the graph shape is not the cause.
- 55 tests pass, including one live run. Tests for the removed nodes and paths were deleted.

## D-037 A `record_denial` node, so every decision leaves one entry in the action log (user decision)
- DENY used to go straight to `finish` and leave the action log empty. Now DENY -> `record_denial` -> `finish`, symmetric with `record_approval` and `record_escalation`. It records a new `Action` type, `record_denial`, with the decision's rationale as the reason and the cited documents.
- Why: an audit trail of what was decided and why (for disputes and chargebacks), and a cleaner eval invariant: a normal run records exactly one entry, and an empty log means something went wrong instead of "maybe a denial".
- The corpus does not require logging denials (OPS-01 says a clear denial needs no action); this is our own design choice. The action log now means "what was decided and done", not only side effects.
- The unknown-order branch still records one `open_escalation`, so that path also has exactly one entry.
- Live checks after adding it (single runs, not evals): a used and muddy jacket with a change-of-mind request gave DENY with one `record_denial` entry, as designed (it cited CAT-09, SEA-05, and the superseded ARC-01, so a stale document reached the decision even on a correct denial). A change-of-mind request on the perishable gift basket (JP-1005, "gourmet gift basket") was wrongly APPROVED and cited SUP-02 and POL-12: the message-only query matched "gift" and retrieved the gift-return policy instead of CAT-05, and the model then applied gift-return rules (store credit) that we scoped out (D-023). Both are v1 retrieval failures worth turning into dataset cases.

## D-038 Keep the record nodes and the action log (user decision)
- Considered dropping `record_approval`, `record_escalation`, `record_denial`, and `ActionLog`, and letting the evals read the label and `approved_action` from the decision. Kept them.
- Why: they are the seam where real integrations (RMA creation, ticketing, case notes) would plug in, they give every run exactly one recorded entry, and they keep the "agent that takes actions" story visible in the diagram and the results.
- Known weakness, to state in the README: in the mock setup the entries are derived from the decision and only appended to an in-memory list, so they add little information beyond it. The one failure they can still surface is an APPROVE with no `approved_action`.

## D-039 Recorded actions live in the graph state; the `ActionLog` class is gone (user decision; supersedes the action-log part of D-033)
- The record nodes (and `order_not_found`) now return `{"actions": [Action(...)]}`; `actions` is a state field with an add reducer, and `finish` copies it into `result.actions`. `ActionLog`, its test, the `action_log` config key, and `run_agent`'s `action_log` argument are removed. `run_agent(request, order_db=None)` is all that is left.
- Why: simpler (one class and one config key fewer), and the recorded action shows up in each node's LangSmith output instead of only in the final result. The evals are unaffected: they score `result.actions`, the same field as before.
- The record nodes no longer need the graph config; only `load_order` uses it (for the order database).
- Still true from D-038: the entries are derived from the decision, so they add little beyond it; this change did not alter that. Earlier entries that mention the action log describe the previous design.
- 57 tests pass, including one live run.

## D-040 Removed the `finish` node; `run_agent` builds the `AgentResult` (user decision)
- Once actions lived in the state (D-039), `finish` only merged two things the state already held. Removed it, and the `result` state field. The three record nodes now go straight to END. `order_not_found` returns a `decision` (a full ESCALATE) and an `actions` entry instead of its own result, so every run ends in the same shape: `decision` plus `actions`.
- `run_agent` now assembles `AgentResult(**decision, actions=actions)` from the final state. Anyone invoking the graph directly gets the raw state and must assemble the result themselves; only `run_agent` does today.
- Lost: the merge no longer appears as its own step in the LangSmith trace (trivial). Gained: one node and three edges fewer, and no special case for the unknown-order path.
- 57 tests pass, including one live run.

## D-041 Two more approved actions: `create_reshipment` and `create_replacement` (user decision)
- Why: the corpus describes approved outcomes that had no action to record: a lost or missing package is reshipped or refunded (POL-11), a defective item is refunded or replaced (POL-10), a custom item with a production error is remade or refunded (CAT-07). Without them the model had a correct APPROVE and no valid `approved_action`, so `record_approval` recorded nothing.
- Added to `Action.type` and to `approved_action` (with guidance on when each applies in the field description). Both carry the item id and no refund amount. The diagram and the mock-data doc list them.
- The other cause of an APPROVE with no recorded action remains (the model leaves the optional field empty), by design (D-029); the evals check for it.

## D-042 Sample runner: `python -m tests.agent.run_sample`
- Runs one request (`--order`, `--message`, `--today`, optional `--now`) or one or all of 11 named samples (`--sample NAME|all`, `--list`) and prints the decision, actions, cited documents, reply, and a link to the LangSmith trace. Samples use the demo orders in `data/seed.sql`; they are for eyeballing traces, not evals.
- First run (`cancel`, order JP-1007, status `processing`): the agent did not cancel. It asked the customer whether the order had shipped, cited CAT-04 and ST-WA, and the message-only query did not retrieve POL-14 (cancellations). It also ignored the order's own `status` field. Another v1 retrieval failure to turn into a dataset case.

## Observation log: repeated jacket run (not an eval)
- Same request (jacket, wrong fit, TX, Basic, JP-1001) run 6 times: all APPROVE with refund 139.55, `label_fee=0`, `outbound_shipping_refund=9.95`. Correct: 121.65 (label fee 7.95, no shipping refund). The calculator computed each input correctly; the inputs were wrong.
- Cause: retrieval returned SUP-02, POL-13, CAT-07, CAT-01. POL-05 (label fee amount) and POL-08 (shipping refunded only when the whole order is returned for our-error reasons) were not retrieved. The model assumed a zero fee instead of escalating, and copied the 9.95 shipping charge from the order and treated it as refundable.
- Implication for v2: metadata filtering (status, authority, state, category) will not add POL-05 or POL-08, which are core documents with no state or category. The fix probably needs query enrichment (add the item category and ship-to state to the query), a larger k, or always-included core documents. Decide when designing v2.
- Concurrency notes for the evals: never share one `OrderDatabase` across threads (SQLite raised "bad parameter or other API misuse"; `run_agent` makes its own per run, so it is safe); warm up the Chroma client with one retrieval before running many runs at once (first-time initialization raced: "Could not connect to tenant default_tenant").

## D-043 Reference answers come from the `GROUND_TRUTH.md` worked examples; no reference oracle (user decision, 2026-09-30)
- Decision: the eval cases are built from the worked examples in `GROUND_TRUTH.md` (sections A to G, plus the stale-doc traps and adversarial cases). Each case's reference decision, refund amount, and gold doc ids are copied into the dataset once, at build time. The evaluators compare the agent's output to those stored labels. Nothing reads `GROUND_TRUTH.md` at eval time, and it never reaches the agent or the LLM judge (hard rule 1 unchanged).
- User requirement: full coverage of the worked examples, including the tricky ones (stacking, tier at purchase, boundary days, holiday and Florida windows, doorbusters, stale-doc traps, escalation and adversarial cases).
- Alternative considered: a reference oracle, a small Python function that encodes the rule tables in section 1 of `GROUND_TRUTH.md` and computes the decision and amount for any order. It would let us generate many varied cases, but it is a second copy of the policy that must be written, checked, and kept in sync. That extra work is not needed for a take-home where the provided worked examples already cover the tricky cases.
- Why: fewer moving parts, and the labels are exactly what the answer key says. A grader has to be independent of the agent; a copied key is.
- Departs from hard rule 3 and from `02-corpus-and-answer-key.md` ("reference amounts/dates are computed by code"). Reference amounts are now copied, not computed. The user has lifted that rule for reference labels. Amounts inside the agent (the calculator tools) are still computed by code.
- Costs to state in the README: (1) the case count is capped at about 75, so thin slices are possible; (2) some worked examples are loose (a refund given as a formula, or two outcomes in one row), so building those cases means choosing concrete item prices and computing the label, and each such choice is recorded; (3) if a policy doc changes, the affected labels must be found and updated by hand; (4) where the key disagrees with a doc the doc wins, so labels need spot-checking against the docs.
- The "Reference oracle" node is removed from `design/eval-loop.md` and not replaced. The answer key is a source used once to author the dataset, not a step in the eval loop, so the diagram starts at the dataset. Each case keeps a `case_id` (A4, B2, ...) naming the worked example it came from, so a reviewer can trace it and spot-check labels. The README should say the cases were written from the provided answer key.

## D-044 The LLM judge compares the reply to the docs retrieved in that run (user decision, 2026-09-30)
- Decision: for the "invented policy" check, the judge gets the customer message, the agent's reply, and the policy text the agent actually retrieved for that run (from the run's output or trace). It does not get the case's gold docs, and never `GROUND_TRUTH.md` (hard rule 1).
- Alternative considered: give the judge the text of the gold docs for each case. Cleaner as a comparison, but it only works if the gold-doc lists are complete, and the approach does not scale: a bigger system cannot look up every gold doc for every case.
- What this check now measures: whether the reply is grounded in what the agent saw, not whether it is correct policy.
- Known limits, to state in the README: (1) if retrieval misses the right doc and the reply states the correct rule from the model's memory, the judge flags it as unsupported, which is the right call (it is ungrounded) but the cause is retrieval; (2) if retrieval returns a stale doc and the reply repeats its rule, the judge sees it as supported and does not flag it. The stale-doc and decision checks catch that case, not the judge.
