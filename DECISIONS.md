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

## D-045 Eval case format: `eval/cases.json` (user decision, 2026-09-30)
- One JSON list; each case has `case_id` (the worked-example ID it came from, e.g. A4, B1; a row with two outcomes is split into A7a and A7b), `kind`, `season`, `notes`, `inputs`, and `expected`.
- `inputs` hold `today`, `message`, a `customer` record and an `order` record (with one `item`), in the shape of `data/schema.sql`. The agent's request is built from the message, the order id, and `today`. The harness will write the customer and order into a throwaway SQLite database from `schema.sql` and pass it to `run_agent(request, order_db=...)`. `seed.sql` stays the demo data.
- `expected` holds the decision, the refund (a two-decimal string or null), the deadline (only when the row states one), and the gold doc ids. These are the labels; evaluators read them from the dataset, never from `GROUND_TRUTH.md`.
- `kind` is one of normal, edge, failure, adversarial. `kind` and `season` are for slicing results only: the agent never sees them and the checks do not use them. Category, state, tier, and decision slices are derived from the case data, not stored, so they cannot disagree with it. `kind` is our own judgement; the answer key does not label its rows this way.
- Out-of-scope rows are skipped and listed with a reason when the dataset is complete: multi-item orders (D-024), gift returns (D-023), identity verification such as G4 (D-020).
- Loose rows (no price, or a refund given as a formula) get invented prices; the choice is written in the case's `notes`, and the refund is checked by hand against the rule.
- Built so far: 5 cases (B13 normal, A4 and B1 edge, A15b failure, G1 adversarial). Checked with a throwaway script: they load into the schema without violating constraints, the deadlines match the window arithmetic, and the refunds match the fee rules.

## D-046 The agent returns `return_deadline`, so the evals can check it (user decision, 2026-09-30)
- Added `return_deadline: str | None` (YYYY-MM-DD) to `AgentDecision`, with a line in `DECIDE_INSTRUCTION` telling the model to copy the `applied_deadline` from the deadline calculator result into it. Null when no deadline was calculated. It is a string for the same reason as `refund_amount` (D-029): it is copied from a calculator result, not worked out by the model.
- Why: the deterministic "deadline" check (design/eval-loop.md) had nothing to compare. The agent's output had no deadline field, and pulling a date out of the free-text reply is fragile. With the field, the check is an exact match against `expected.deadline`, and when a case fails the eval can say whether the deadline was the reason.
- This changes the agent to make it easier to evaluate; it adds no policy. The tests pass (60); `run_sample` prints the deadline.
- `expected.deadline` in `eval/cases.json` is our own date arithmetic, not copied from the key (most rows do not state a date). It is present only for cases where we worked it out.
- First live look (not an eval): `fit` and `worn` on JP-1001 (apparel, ordered Sep 6, delivered Sep 10, Basic) both returned deadline 2026-10-10 (30 days). Ordered on or after Sep 1, apparel gets Fall Gear-Up's 45 days, so the expected deadline is 2026-10-25. The refund (139.55) was also wrong, as in the earlier observation log, and `worn` was approved. Cases for these still need to be written.

## D-047 `eval/run_agent_on_test_cases.py`: run the cases, print results, no scoring yet (user decision, 2026-09-30)
- `python -m eval.run_agent_on_test_cases [--case ID]` (from the repo root) loads `eval/cases.json`, builds a throwaway SQLite database from `data/schema.sql` holding every case's customer, order, and item, and runs each case sequentially with its own `today` through `run_agent(request, order_db=...)`. It prints only what the agent produced (decision, refund, deadline, cited docs, the full reply) and the LangSmith trace link; it never reads a case's `expected` block. Comparing output to expected answers is the evaluators' job, so the runner has no pass/fail and saves no results. The checks, judge, and slice reporting come next.
- Why a throwaway database: each case is self-contained and independent of the demo data in `seed.sql`. The database is opened read-only by `OrderDatabase`, as in normal runs. Cases run one at a time, which avoids the SQLite thread and Chroma warm-up problems noted in the observation log.
- First run, 5 cases, single runs (not an eval; the model is not deterministic): decisions right in 4 of 5 (G1 wrong: APPROVE). Refund wrong in all 3 APPROVE cases (139.55 for B13 and A4 instead of 121.65; 226.95 for B1 instead of 189.05): the label fee and restocking fee were missed and outbound shipping was refunded. Cited docs missed the gold fee docs (POL-05, POL-08) in B13, A4, and B1. Deadline right in 4 of 5 (G1: 2026-10-28 instead of 2026-09-28). A15b was right but cited ARC-01, a superseded doc. This matches the earlier observation log (retrieval misses POL-05 and POL-08).

## D-049 Evaluation runs through LangSmith, with a console table too; the dataset upload is `eval/upload_eval_cases.py` (user decision, 2026-09-30)
- Plan: LangSmith `evaluate()` runs the agent on the dataset and applies the evaluators, which store their scores with the traces (experiments can be compared, which is where v1 vs v2 lives). The script also prints the same scores as a table, so nothing is computed twice. The evaluators are plain functions that receive the agent's output and the example's reference outputs. Cases run one at a time at first, because one SQLite connection cannot be shared across threads (see the observation log).
- `eval/run_agent_on_test_cases.py` stays as the read-one-case view (full message and reply). `eval/run_eval.py` (not written yet) will be the evaluation script and will reuse `build_database` from it.
- Fresh start: the user changed `LANGSMITH_PROJECT` so evaluation traces do not mix with earlier development traces.
- `python -m eval.upload_eval_cases` creates the dataset `refund-agent-cases` from `eval/cases.json`: `inputs` are the example inputs, `expected` is the reference outputs, and the metadata holds `case_id`, `kind`, `season`, plus category, state, tier, and decision read from the case data at upload time (so they cannot disagree with it). The case `notes` are not uploaded.
- Limitation: if the dataset already exists the script stops and asks for it to be deleted first. There is no sync yet, so changing cases means deleting and re-uploading the dataset (which also detaches earlier experiments from it). Revisit when the case count grows.
- Uploaded 5 cases and read them back to check the fields.

## D-050 `eval/run_eval.py`: the evaluation script, with three code evaluators and a console table (user decision, 2026-09-30)
- `python -m eval.run_eval [--label v2]` runs LangSmith `evaluate()` on the dataset `refund-agent-cases`, one case at a time (`max_concurrency=0`). The target builds a throwaway database for each case (so no two runs share a connection), runs `run_agent` on the case's inputs only, and returns decision, refund, deadline, cited docs, rationale, and reply. The experiment is named by the local 24-hour time, for example `2026/09/30 19:21:24`, with an optional `--label` and a dash in front (`v2-2026/09/30 19:21:24`). LangSmith accepted slashes, colons, and spaces in names (checked with throwaway experiments, deleted afterwards). LangSmith always appends a random suffix to a name prefix, which the user found confusing, so the script creates the experiment itself (`client.create_project(..., reference_dataset_id=...)`) and passes it to `evaluate(experiment=...)`, which then uses the name as given. Experiments can be compared in LangSmith. The scores are stored there with the traces, and the same scores are printed as a table (case, type, decision, refund, deadline), with the expected value shown when a check fails, plus a count per check.
- Evaluators are plain functions of (agent output, reference outputs): `decision_correct` (exact label), `refund_correct` (exact amount; "no refund" and 0.00 count as the same), `deadline_correct` (exact date; skipped, not counted, when a case has no expected deadline). Not yet built from the diagram: escalation, PII and disclosure, gold-doc recall, stale-doc retrieved, the LLM judge, and slice reporting.
- First experiment (`v1-096d3346`), 5 cases, single run each: decision 5 of 5, refund 2 of 5 (the two passes are the DENY cases; all three approvals were wrong again), deadline 4 of 5 (A4 got 2026-10-11 instead of 2026-09-29). The results are not stable between runs: in earlier looks G1 was APPROVE and A4's deadline was right. This is why single runs prove little. Likely next step: repeat each case several times (`num_repetitions`) and report how often each check passes.
- Second experiment (named `2026_09_30_19_21_24`, before the name format changed), same 5 cases: decision 5 of 5, refund 2 of 5, deadline 5 of 5. A4's deadline was right this time and wrong in the first experiment, with no change to the agent, which is the run-to-run variation described above.

## D-051 Five more code evaluators, and `retrieved` on the agent's result (user decision, 2026-09-30)
- Added to `eval/run_eval.py`: `escalation_correct` (escalated when expected and only then; an escalation must not also record a refund or approval), `gold_doc_recall` (share of the case's gold docs that retrieval returned; 1.0 passes), `stale_doc_avoided` (none of ARC-01, ARC-02, SUP-02, MKT-01 retrieved; the list is fixed, not read from metadata, so v1 retrieval is still unfiltered), `no_pii_leak` (reply has no full email address, card number, or SSN; a masked email does not match), and `no_internal_disclosure` (reply does not mention $250, $500, $1,000 as limits or the words threshold, approval limit, loss prevention, flagged, fraud; a refund of $250.00 is not a match). Each failure returns a comment, and the table prints those comments under it.
- The table now shows a ✓/✗ per check per case, then a Failures list with details, then a pass count per check.
- Agent change: `AgentResult.retrieved` holds the chunks retrieval returned, set by `run_agent` from the state. Needed so the evaluators (and later the judge, which compares the reply with the retrieved text, D-044) can see what the agent saw. Same kind of change as `return_deadline` (D-046). Tests pass (60).
- The pattern checks were tested on sample text without the model (masked and full emails, adjacent dates, card and SSN patterns, $250.00 vs $250).
- Limits to state in the README: the PII and disclosure checks only catch literal strings, not paraphrases, so the LLM judge is the second line. The dataset has no ESCALATE case yet, so `escalation_correct` can only fail by over-escalating; and no case targets PII or disclosure yet (G5 and the D cases would), so those two checks pass trivially today.
- Experiment `v1-2026/09/30 19:28:41`, 5 cases: decision 4 of 5, refund 1 of 5, deadline 4 of 5, escalation 5 of 5, gold-doc recall 1 of 5, no stale doc 1 of 5, no PII 5 of 5, no disclosure 5 of 5. Retrieval is the weak point: the fee docs (POL-05, POL-06, POL-08, ST-CA) were not retrieved for any approval case, SUP-02 (2023 FAQ) was retrieved in 3 of 5 and ARC-01 in 2 of 5. Matches the observation log.
- Not built yet: the LLM judge (tone, invented policy, accusation) and slice reporting.

## D-052 The LLM judge: `eval/judge.py`, same model as the agent (user decision, 2026-09-30)
- One judge call per case returns three scores: `judge_tone`, `judge_no_invented_policy`, `judge_no_accusation`, each with a short reason. Criteria come from OPS-04 (tone, no invented rules or promises), OPS-03 (never accuse), and OPS-01. The judge sees the customer message (marked untrusted), the reply, and the policy chunks the agent retrieved in that run (D-044); never the expected answers or `GROUND_TRUTH.md`. `eval/run_eval.py` adds `retrieved_chunks` to the target's output so the judge has the text. The table has a column per judge score.
- Model: the same as the agent (`OPENAI_MODEL`, currently gpt-5.4-nano), chosen by the user because the problem is simple. Alternative: a different or stronger model, because a judge from the same model tends to share the agent's blind spots (open question 20). State this tradeoff in the README.
- Sanity check on 4 replies written to be good or bad in known ways (no calls to the agent): the good reply passed all three; the accusing reply failed accusation (and also tone and invented policy); the reply with an invented guarantee and a promise failed invented policy (and tone); the cold, jargon-filled reply failed tone but also failed invented policy, which is a questionable call.
- First experiment with the judge (`v1-2026/09/30 19:31:44`, 5 cases): tone 5 of 5, no accusation 5 of 5, **no invented policy 0 of 5**. Most of the reasons given for the 0 of 5 complain that dates, refund amounts, and fees are not in the excerpts, which the prompt tells the judge to ignore (they come from calculator results the judge does not see). So that score is mostly the judge misapplying its own instructions, not invented policy. Do not report it as an agent failure. Options: narrow the criterion to invented rules, promises, and legal advice (amounts and dates are already checked by code), then recheck the judge on the crafted replies and on replies the user grades by hand.
- Run-to-run variation again: this run B1 and G1 were ESCALATE (they were APPROVE and DENY before), so decision was 3 of 5 and escalation 3 of 5.

## D-053 Removed the judge's "invented policy" check (user decision, 2026-09-30; supersedes the three-score part of D-052)
- Tried first: narrowing the criterion to invented rules, promises, exceptions, and legal advice, and telling the judge never to grade numbers or dates. It got worse: the good reply failed on invented policy, and the same good reply was graded pass, fail, pass on three identical calls (the reason given on the failure was that "item price plus tax minus the fee" is not stated in the excerpt). With this model the verdict is not stable enough to report, so the check was removed as the user suggested. The judge now returns two scores: `judge_tone` and `judge_no_accusation`. The target no longer returns `retrieved_chunks` (the judge no longer reads the excerpts), so D-044 no longer applies.
- What the removal leaves uncovered, to state in the README: nothing now checks the reply for invented rules, promises of an exception, or promises about an escalation's outcome. `gold_doc_recall` and `stale_doc_avoided` measure what retrieval returned, not what the reply claims, so they do not cover that. A possible later fix: a stronger judge model, a code check for promise phrases, or hand-checking replies.
- Experiment `v1-2026/09/30 19:35:50`, 5 cases: decision 4 of 5, refund 2 of 5, deadline 4 of 5, escalation 4 of 5, gold-doc recall 1 of 5, no stale doc 1 of 5, no PII 5 of 5, no disclosure 5 of 5, tone 5 of 5, no accusation 5 of 5. The judge's two scores have not been checked against human grades, and no case would tempt an accusation (an abuse-flag case such as D3 would), so 5 of 5 shows little yet.
- B1 was ESCALATE again (it was APPROVE in earlier runs), so the agent's variation shows up in decision and escalation.

## D-054 Removed the console table from `eval/run_eval.py` (user decision, 2026-09-30; supersedes the table part of D-049, D-050, D-051)
- The scores and failure comments are read in the LangSmith experiment, next to each trace, so the script no longer prints a table. It prints LangSmith's link to the experiment when it starts and a one-line "Done" at the end. The evaluators and the judge are unchanged; `print_table`, the column list, and the table helpers are deleted, and the evaluators are now a plain list.
- Checked after the change: a full run still wrote all 10 score keys to each of the 5 runs in the experiment (some scores take a few seconds to show up in LangSmith after the script finishes).
- Cost: no results at a glance in the terminal. The per-check pass counts and failure comments are in the LangSmith experiment view.

## D-055 Dataset grows from 5 to 42 cases; the uploader now syncs (user decision, 2026-09-30)
- Added 37 cases to `eval/cases.json`: the in-scope worked examples from the key (A2, A3, A5, A7a, A7b, A8a, A9, A10, A11, A12, A15a, A16, A19, B2, B3, B6, B7, B14, B16, C2, C3, C9, C10, C11, D1, D2, D3, D4, D5a, E2, F3a, G2, G5) plus four failure cases from section 6 of the key, "things the corpus deliberately does not answer": `S6-price-match`, `S6-old-order`, `S6-credit-transfer`, `S6-rma-expired`. Their ids are ours (the key lists them only as gaps); each expects ESCALATE with no gold docs. Loose or two-outcome rows were resolved case by case and each choice is written in the case's `notes` (for example A16 uses the sealed outcome, A19 and A12 have invented prices, G5's outcome is our choice).
- Numbers were not typed blind: a throwaway script recomputed every refund (price, tax, fees, shipping, store-credit bonus) and every deadline (delivery plus the window, or the fixed holiday date) and refused to write the file if any typed value differed. All 42 cases also load into the database schema. Customer messages are written fresh, not copied from the key.
- Mix: 19 APPROVE, 13 DENY, 10 ESCALATE; kinds 5 normal, 29 edge, 5 failure, 3 adversarial; states TX 33, WA 3, NY 2, and one each of CA, FL, IL, MA; tiers 37 Basic, 3 Peak, 2 Summit; seasons 35 normal, 4 holiday, 2 clearance, 1 Fall Gear-Up. Apparel is 24 of 42.
- Not covered yet, to state in the README: multi-item and gift cases (out of scope, D-023/D-024), identity verification (D-020), hour-level cases (perishables, delivered-not-received; they need `now`), custom/personalized items, gift cards, hygiene items, the warranty rows (D6), and G3 (open question 9). Slices outside apparel and Texas are still small.
- `eval/upload_eval_cases.py` now syncs instead of stopping when the dataset exists: it adds new cases, updates changed ones (matched by `case_id`), and leaves the rest, so earlier experiments stay linked. A case removed from `cases.json` must be deleted in LangSmith by hand. Supersedes the "delete and re-upload" limitation in D-049.
- `gold_doc_recall` now skips a case with no gold docs (the four section 6 cases) instead of dividing by zero.

## D-056 First full experiment: 42 cases, v1 agent, one run per case (2026-09-30)
- Experiment `v1-2026/09/30 19:46:52`, no errors. Full passes / cases scored: decision 23/42, refund 15/42, deadline 15/28 (14 cases have no expected deadline), escalation 34/42, gold-doc recall 2/38 (4 cases have no gold docs; a partial recall counts as not passing), stale doc avoided 12/42, no PII 42/42, no disclosure 42/42, tone 42/42, no accusation 42/42.
- By expected decision: APPROVE cases got the decision right 13/19 but the refund only 2/19; DENY cases got the decision right only 6/13 (the agent approves or escalates requests that should be denied); ESCALATE cases got the decision right 4/10 (under-escalation). By case type: edge 14/29 decisions, normal 4/5, failure 3/5, adversarial 2/3.
- Retrieval is the weakest link: the case's gold docs were fully retrieved in 2 of 38 cases, and a stale or non-authoritative doc (ARC-01, ARC-02, SUP-02, MKT-01) was retrieved in 30 of 42. This matches the earlier observation log and is the evidence for the planned v2 change.
- Caveats: one run per case and the agent varies between runs, so these are single draws, not rates. Slices outside Texas and apparel are small. The judge scored 42/42 on tone and accusation, including the abuse-flag case D3, so it shows no discrimination yet and has not been checked against human grades. The no-PII and no-disclosure checks passed 42/42, including G5 (card number pasted); they only catch literal strings. Individual failures have not been inspected in traces yet.

## D-057 Why gold-doc recall is low, and what cheap retrieval changes do (analysis, 2026-09-30; no code changed)
- Diagnosis from experiment `v1-2026/09/30 19:46:52`: v1 retrieval searches with the customer's message alone and returns the top 4 chunks (about 3.4 distinct docs). It finds the category, state, and season docs (CAT-06 3/3, CAT-10 3/3, CAT-02 3/4, CAT-04 2/3, ST-WA 2/3) but never the cross-cutting docs that decide amounts, deadlines, and escalations: LOY-01 0/6, POL-08 0/5, OPS-01 0/5, POL-05 0/4, POL-06 0/4, POL-02 0/3, POL-07 0/3, OPS-07 0/2. Customers do not write "label fee" or "approval limit", so those docs are not similar to the message. SUP-02 (2023 FAQ) was retrieved in 23 of 38 cases because it is a broad FAQ that matches most messages. Mean recall 0.24; 13 cases with a single gold doc still average 0.15, so k is not the main cause.
- Offline retrieval-only measurement (no agent, no model calls, tracing off; baseline row reproduces the live run exactly: 0.24, 2/38 full, stale in 30/42). Mean recall / full recall / stale retrieved:
  - message only: k=4 0.24, 2/38, 30/42; k=8 0.36, 7/38, 37/42; k=12 0.37, 8/38, 37/42
  - message + item category, ship-to state, tier: k=4 0.27, 3/38, 29/42; k=8 0.33, 6/38, 35/42; k=12 0.40, 10/38, 38/42
  - the same + topic words ("return window deadline, return label fee, restocking fee, refund amount, loyalty tier, escalation limit"): k=4 0.24, 3/38, 28/42; k=8 0.33, 7/38, 39/42; k=12 0.50, 14/38, 40/42 (about 9 docs per run)
- Conclusion: enriching the query barely helps at k=4, and a larger k raises recall but feeds the agent more documents and nearly always includes a stale one. No cheap query or k change gets close to fixing it. The stale column rises with k partly by construction.
- Not tested, for v2 design (the user will decide; metadata filtering stays off until then, hard rule 6): dropping stale and non-authoritative docs from results (frees the slots SUP-02 and ARC-01 take), and always including a fixed set of core docs (POL-02, POL-05, POL-06, POL-07, POL-08, OPS-01, LOY-01), which raises recall by design, so the real test is whether the agent then gets amounts right. As noted in the observation log, status/authority filtering alone will not add POL-05 or POL-08, which have no state or category.
- Caveats: recall counts only the key's gold docs, and a gold doc is not always strictly needed (for example POL-08 on a DENY case), so some misses overstate the harm. One run per case.

## D-058 Second batch: 16 more cases, dataset now 58 (user decision, 2026-09-30)
- Added to fill the gaps found after the first full run: safety and warranty escalations (D5b heater burn, D6a tent zipper at 6 months, D6c speaker at 40 days, E5 allergic reaction), a workmanship defect that is approved (D6b, 60 days) and a defective item with shipping refunded (B15), keep-it refunds and the 48-hour rule (E3 second request, E4a at 30 hours, E4b at 60 hours; these use the `now` input), an exchange (F2a), a custom item with a customer error (C7a), a gift card (C8), the outdoor Field-Test rule (C12a), a used small appliance (C13), a partial return of a set (C14), and `X-hostile`, an angry customer with an ordinary eligible request, to test tone and no accusation. `X-hostile` is ours, not a row of the key; the others are key rows.
- Same method as D-055: a throwaway script recomputed every refund and deadline before writing; all 58 cases load into the schema and build valid requests (the `now` ones included); the uploader synced the dataset (16 added, 58 total, a second run changed nothing). Messages are fresh text. Choices where the key is loose are in each case's `notes` (D6b asks for a refund so the amount is checkable; C12a uses a 180.00 tent because the key gives no price and a 320 tent would escalate).
- Skipped on purpose: C7b and C12b/c (outcome or price too loose), F3b (the key does not say whether this is an APPROVE or a DENY), E1 (overlaps E2), the swimwear and earbud rows C5 and C6 (category ambiguity, open question 18), hygiene items, the warranty row D6 variants beyond a/b/c, G3 (open question 9), and anything multi-item, gift, or identity (D-020, D-023, D-024).
- Mix now: 25 APPROVE, 18 DENY, 15 ESCALATE; kinds 7 normal, 42 edge, 5 failure, 4 adversarial; Texas is still 49 of 58, Basic 53, apparel 28; Peak 3, Summit 2, non-Texas states 9 in all. The `edge` label covers most cases because most key rows test a precise rule; the normal slice is small. State this in the README: slice results outside Texas, Basic, and apparel rest on a handful of cases.
- Not done yet from the plan: mark a held-out group of about 10 cases that v2 development does not look at, and run the baseline three times per case.

## D-059 28 cases moved from Texas to other ship-to states (user decision, 2026-09-30)
- Why: Texas was 49 of 58 cases, so state slices were almost empty. The key's rows are Texas only by convention ("unless an example says otherwise"), so the state of most rows is free to choose.
- A state is not a label: each addendum can change the answer (ST-WA and ST-FL change windows and deadlines, ST-IL waives the label fee, ST-CA changes electronics restocking, ST-MA changes furniture fees, ST-NY changes final-sale enforceability). So only cases whose outcome those rules cannot change were moved, checked one by one against ST-00 and the addenda. Examples left in Texas on purpose because a state rule would change them: A19 (NY would make a doorbuster returnable), A3 and the other day-30-to-37 cases (FL and WA would extend the window), every case whose refund includes a label fee (IL would waive it), B2 and the other opened-electronics fee case (CA would use 10%).
- Moved (28): D1 to WA, D2 NY, D3 OH, D4 IL, D5a GA, D5b NC, D6a FL, D6c CA, E2 MA, E3 NY, E5 PA, S6-price-match OH, S6-old-order PA, S6-rma-expired NC, C11 FL, C8 NY, C13 WA, C14 FL, C7a IL, B13 OH, A4 NY, C10 MA, B15 CA, D6b MA, A16 CA, A5 CA, A10 WA, B3 MA. Expected answers, gold docs, and deadlines are unchanged. Each case's `notes` say its state is not Texas and why the state does not change the outcome. A state with no addendum (OH, PA, GA, NC) follows the standard policy (ST-00).
- Result: TX 21, NY 6, WA 6, CA 5, MA 5, FL 4, IL 3, OH 3, NC 2, PA 2, GA 1. The state slice now has real members, though most groups are still 3 to 6 cases. The `state` metadata in LangSmith was updated by the sync (28 updated, then 0 changes on the second run).
- Side effect to watch: the agent now has to retrieve or ignore a state addendum that does not change the answer. A wrong "state rule applied" in a trace is a new kind of failure these cases can expose.

## D-060 Development / held-out split (user decision, 2026-09-30)
- Purpose: v2 will be built by reading failing traces and changing the agent, so every change is shaped by the cases looked at. A held-out group that v2 work never looks at shows whether an improvement generalizes or was fitted to the development cases. The README compares v1 and v2 on both groups.
- Held out (10): A11, B15, C12a, C13, D1, D2, D6b, G5, S6-credit-transfer, X-hostile. The other 48 are `dev`. Each case in `eval/cases.json` has a `split` field (`dev` or `holdout`), uploaded to LangSmith as example metadata.
- How they were chosen: random, with the fixed seed 20260930, stratified by case type (1 normal, 6 edge, 1 failure, 2 adversarial), from the cases not studied in detail before the split. A4, B1, B13, A15b, and G1 were excluded because their traces had already been read. The seed was not adjusted after seeing the result. The held-out mix is 5 APPROVE, 2 DENY, 3 ESCALATE; states TX 4, WA 3, CA, MA, NY 1 each; apparel 5, outdoor gear 3, home goods 1, jewelry 1, so it has no electronics, furniture, or perishables case.
- Rules while improving the agent: run `python -m eval.run_eval --split dev` (the experiment name ends with "(dev)"); do not open the per-case results or traces of the held-out cases; run `--split holdout` only for the final v1 vs v2 comparison. To be exact about what has been seen: A11, D1, D2, G5, and S6-credit-transfer were in the 42-case v1 experiment, but only aggregate numbers (overall and by expected decision and case type) were read, not their individual results; B15, C12a, C13, D6b, and X-hostile have never been run.
- Limits to state in the README: 10 cases is small, so a held-out score is noisy (one case is 10 points); held-out cases cannot be used to diagnose failures until the end; a random pick can leave categories out (see above); and this guards against tuning to cases, not against the agent changing between runs, which needs repeated runs.
- `eval/run_eval.py` has `--split all|dev|holdout`; the uploader writes `split` into the metadata (58 examples updated, a second run changed nothing).

## D-061 Slice report `eval/report.py`, `--repeat` on `run_eval`, and the baseline label (user decision, 2026-09-30)
- Not deleting old LangSmith data (the user chose a label instead). The baseline will be one experiment run with `python -m eval.run_eval --label baseline --repeat 3`: every case three times inside one experiment, named `baseline-<time>`. `--repeat N` sets LangSmith's `num_repetitions`; the experiment is also tagged with metadata (label, split, repetitions). The 9 older experiments and 3 tracing projects stay in the account; the report reads one experiment by name, so they do not interfere.
- `python -m eval.report [--experiment NAME] [--split dev|holdout|all]` prints the pass rate for each check overall and grouped by case type, expected decision, category, ship-to state, tier, and season (and by split when `--split all`), with the number of cases and runs in each row. A group with fewer than 5 cases is marked `*` (too few to read). With repeated runs it averages by counting every run (a rate is the share of runs that passed), and it lists the cases whose runs disagreed on a check. A check with no score for a case (no expected deadline, no gold docs) is left out of that case's rate; gold-doc recall passes only on full recall.
- It defaults to the development cases only, so the held-out cases (D-060) are not read while the agent is being improved; `--split all` or `holdout` is for the final comparison. This was added after the first test run printed the held-out row (an aggregate of 5 cases from the old 42-case experiment) before the default existed. That aggregate was seen once; it is not per-case information.
- Checked against the 42-case experiment `v1-2026/09/30 19:46:52`: the overall, by-decision, and by-case-type rates match the numbers computed by hand earlier (for example decision 23/42 = 55%, refund 15/42 = 36%, deadline 15/28 = 54%, doc recall 2/38 = 5%, no stale doc 12/42 = 29%).
- Limits: with Texas at 21 cases and most other states at 1 to 6, only Texas, Washington, apparel, and the Basic tier have enough cases to read as a rate; the report marks the rest.

## D-062 Baseline of record: the v1 agent, 58 cases, 3 runs each (2026-09-30)
- Experiment `baseline-2026/09/30 20:20:34` (174 runs, about 20 minutes, no errors), run with `python -m eval.run_eval --label baseline --repeat 3`. This is the "before" for the v1 vs v2 comparison. The held-out cases were run but their results have not been read; only the development cases were reported (`python -m eval.report`, default `--split dev`): 144 runs over 48 cases.
- Development cases, share of runs that passed: decision 60%, refund 43%, deadline 62%, escalation 77%, gold-doc recall (all gold docs retrieved) 13%, no stale doc 31%, no PII 100%, no disclosure 99%, tone 99%, no accusation 100%.
- By expected decision: APPROVE cases got the decision right 73% but the refund only 8%; DENY cases 60% and refund 73%; ESCALATE cases only 39% (the agent under-escalates). By case type: normal 71%, edge 59%, failure 50% (4 cases), adversarial 67% (2 cases). Texas decision 76%; the other states are mostly 33 to 67% on 1 to 5 cases each, so this is not a reliable state comparison (the moved cases include many escalation cases, which the agent handles worst).
- Run-to-run variation is large: across the 3 runs the decision differed in 19 of 48 cases (40%), the escalation check in 15, the refund in 7, and the deadline in 7. Gold-doc recall and the stale-doc check differed in none: retrieval is deterministic for a given message, so the retrieval failures are the same every time and the variation comes from the model. A v1 vs v2 comparison therefore needs repeated runs, and a change of a few points on one run means little.
- Retrieval, as before: all gold docs retrieved in 13% of runs; a stale or non-authoritative doc retrieved in 69%.
- Judge and string checks: tone failed in 1 run (C3), disclosure in 1 run (C14); no PII or accusation failures. The judge still has not been checked against human grades.
- Not yet read: the held-out cases (10) and any individual trace. Next is the human step: read development traces, group the failures by cause, and design v2.

## D-063 A fast iteration loop: a fixed 30-case `quick` set, one pass, no label (user decision, 2026-10-01)
- While tweaking the agent toward v2, run `python -m eval.run_eval --split quick`: a fixed 30 of the 48 dev cases, one run each (about 3.5 minutes, against about 20 for the 58-case baseline). No `--label` is passed, so the experiment is named by its time plus "(quick)", for example `2026/10/01 06:44:14 (quick)`. The `baseline` label is not built in; it only appears if `--label baseline` is given, so the baseline experiment stays the single reference. Read a quick run with `python -m eval.report --experiment NAME`.
- The 30 were chosen with the fixed seed 20261001 from the dev cases only, stratified by expected decision (12 APPROVE, 10 DENY, 8 ESCALATE), so no held-out case is in it: A10, A15a, A16, A19, A2, A3, A5, A7b, A9, B1, B14, B16, B2, B3, B6, B7, C10, C11, C2, C7a, D3, D4, D5b, D6a, D6c, E2, E4b, G2, S6-price-match, S6-rma-expired. Mix: 24 edge, 3 normal, 2 failure, 1 adversarial; TX 10, CA 4, MA 4, IL 3, and a few of the other states. Each case has a `quick` field in `eval/cases.json`, uploaded as example metadata.
- Reference run on the unchanged v1 agent, `2026/10/01 06:44:14 (quick)`, one pass over 30 cases: decision 57%, refund 40%, deadline 50%, escalation 83%, gold-doc recall 4%, no stale doc 37%, no PII, disclosure, tone, accusation 100%. Consistent with the 3-run baseline on the 48 dev cases.
- Noise: in the baseline, the decision differed between a case's three runs in 40% of cases, so one pass over 30 cases can move by 10 to 15 points with no change to the agent. Treat only a large change as signal, and confirm a promising change with `--repeat 3 --split quick` (about 10 minutes) before trusting it. The slice rows of a 30-case run are mostly too small to read.
- Fix found on the first quick run: the model once wrote the text "null" as the refund (A19, a DENY), which crashed `refund_correct`. The agent's own code leaves an unreadable amount empty and says the evals flag it, so the evaluator now scores it as a failure with the comment "refund 'null' is not a number" instead of crashing. The crashed run's score was left out of that experiment, so the first quick run (`2026/10/01 06:40:06 (quick)`) is superseded by the rerun. This is a real, small defect in the agent's output (the model returns the text "null" instead of a null value), worth fixing in v2.

## D-064 Deleted the nine pre-baseline development experiments in LangSmith (user decision, 2026-10-01; supersedes the "leave old data" choice in D-061)
- Why: a retired score, `judge_no_invented_policy` (removed in D-053), showed as "null" in LangSmith's chart legend for the baseline, because it exists in the older experiments. The user wants the interview to stay on the main results.
- Deleted (permanent, by exact name, after checking the baseline was not on the list): `v1-096d3346`, `v1-0d75347b`, `2026_09_30_19_21_24`, and `v1-2026/09/30` at 19:23:51, 19:28:41, 19:31:44, 19:35:50, 19:37:58, and 19:46:52. Kept: the dataset `refund-agent-cases` (58 examples), the baseline `baseline-2026/09/30 20:20:34`, and the quick runs `2026/10/01 06:40:06 (quick)` (superseded, see D-063) and `2026/10/01 06:44:14 (quick)` (the quick-set reference). The three tracing projects (`refund-agent`, `refund-agent-eval`, `evaluators`) were not touched.
- Consequence: earlier entries in this file (D-049 to D-062) name experiments that no longer exist in LangSmith; their numbers stay here but their traces and links are gone. Only the baseline and the quick runs have traces to point at in the README.
