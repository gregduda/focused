# Architecture and workflow (planned; nothing here is built yet)

## Stack (defaults, tell the user before departing)
- Python 3.14 (system default, user's choice, D-010) in a plain venv. Dependencies in `requirements.txt`
  (no pyproject.toml). Verified langchain, langgraph, langchain-openai, langsmith import cleanly on 3.14
  (only a DeprecationWarning from langsmith). `uv` is not installed.
- LangGraph for the agent; LangChain for retriever/model abstractions; LangSmith for tracing + datasets + evals
  (`langsmith` evaluate()). Deep Agents is likely overkill for one task; only add it if the user wants it.
- LLM provider is OpenAI (user decision, D-009). Use `langchain-openai`. Keys `OPENAI_API_KEY` and `LANGSMITH_API_KEY` are in `.env` (gitignored; `env.example` has empty placeholders). Never print or commit key values.
- Model: `gpt-5.4-nano` for both the agent and the LLM judge (user decision, D-011). The name lives in `.env` as `OPENAI_MODEL` (never hard-coded); read it once in a small config module.
  The shared model means self-preference bias is a documented limitation; mitigate with judge calibration
  against human labels and by keeping deterministic checks primary.
- Embeddings: Chroma's local default all-MiniLM-L6-v2, no embedding_function passed (D-019), with a simple local vector store (in-memory or Chroma/FAISS); keep it swappable.

## Intended shape
```
request(order_id, message, today) -> load order/customer tool
   -> retrieve policy chunks (RAG) -> deterministic calc tools -> decision + customer message
   -> action tools (create_rma, keep_it_refund, cancel_order, open_escalation, warranty_ticket)
```
- Structured output: `decision` in {APPROVE, DENY, ESCALATE}, `refund_amount`, `reason_code`, `cited_doc_ids`,
  `customer_message`.
- DECIDED (D-021): calc tools should take parameters the LLM read from
  retrieved docs (window_days, fee %) rather than hard-code policy, or RAG becomes decorative and the eval
  stops measuring retrieval. Date/money arithmetic itself is always deterministic code.
- Mock data: JSON/py fixtures for orders + customers with the README fields. Dataset builder generates
  order records and expected values from code.

## Phases
1. Scaffolding: requirements.txt, .env.example, loader/indexer, mock data schema.
2. Agent v1 (no metadata filtering) + tracing.
3. Dataset: normal / edge / failure / adversarial cases; slices from GROUND_TRUTH section 5.
4. Evaluators: deterministic (decision, amount, window/date, escalation, disclosure/PII regex, cited gold docs,
   retrieval recall of gold docs, stale-doc-retrieved flag) + LLM judge (tone, no-invented-policy, no accusation,
   no threshold disclosure). Calibrate the judge on a small human-labeled set if time.
5. Run v1, inspect traces, write down real failures. Then v2 (status/authority/state/category filtering, only
   after the user says so), rerun, compare per slice. Log honest regressions.
6. README (diagram, quickstart, trace/eval viewing, before/after, limits, prod-eval plan), screen recording.

## File conventions
- `DECISIONS.md`: running decision log. `WHAT_I_CHECKED.md`: user-authored only.
- Keep the agent code small and readable; the user must be able to explain every module.
- Tests: pytest. Must include the "answer key is not indexed" test and date-injection test.
