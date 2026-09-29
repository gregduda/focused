# Eval loop (planned)

How we build, evaluate, learn, and improve. The agent's own flow is in `agent-run-flow.md`.

```mermaid
flowchart TD
    DS[("Eval dataset<br/>normal, edge, failure, adversarial<br/>inputs plus reference decision,<br/>amount, gold doc ids")]
    ORC["Reference oracle<br/>dates and amounts computed by code"] --> DS
    DS --> RUN["Run agent<br/>today passed per case"]
    RUN --> TR[("LangSmith traces")]
    RUN --> DET["Deterministic checks<br/>decision, amount, deadline,<br/>escalation, disclosure, PII,<br/>gold-doc recall, stale doc retrieved"]
    RUN --> JUDGE["LLM judge<br/>tone, invented policy,<br/>accusation"]
    DET --> RES["Results by slice<br/>category, state, tier, season,<br/>decision, adversarial"]
    JUDGE --> RES
    RES --> LEARN["Inspect traces<br/>and failures"]
    LEARN --> FIX["Improve<br/>v2: metadata filtering"]
    FIX --> RUN
```
