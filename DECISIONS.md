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
