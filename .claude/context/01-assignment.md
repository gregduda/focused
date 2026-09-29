# Assignment: "Agent Take-Home Exercise" (Focused Labs), source: `Agent Take-Home Exercise.pdf`

Theme: "Build an Agent You'd Actually Trust." Loop: Build -> Evaluate -> Learn -> Improve.
Reviewers spend ~30 minutes on the submission, then ~1 hour interview (datasets, evals, traces, architecture;
they may hand over a NEW failure case to investigate live).

## Required
- Working agent with at least one useful tool and a retrieval (RAG) step
- At least one eval dataset with expected outcomes: normal cases, edge cases, real-world failures
- Deterministic checks where sensible; an LLM judge where human-like judgment helps
- Inspectable traces
- Before/after eval results: a real first run, an improvement, a rerun
- A few honest failures, tradeoffs, open uncertainties
- Short explanation of how the agent would be evaluated in production

## Submission checklist (README must make the main story easy to find)
- Repo link; README with quickstart; simple agent diagram
- How to view traces and eval runs (LangSmith links/instructions)
- Before-and-after summary
- Short explanation of dataset and evaluator choices
- Known failures and limitations
- Brief screen recording
- A short note on how coding assistants helped and what the user checked themselves (`WHAT_I_CHECKED.md`)

## Optional extras (pick what fits)
Judge calibration vs human labels, sliced results, tool-call/trajectory evals, adversarial examples,
online evaluation, PII guardrails, streaming, setup script/Makefile/Docker.

## Tools they like
LangSmith, LangChain, LangGraph, Deep Agents. Other tools fine if traces/evals are inspectable.

## Values
Perfect scores are NOT the goal. Honest failures and what was learned matter more. A simple, well-built agent
with thoughtful evals beats a sprawling system the user doesn't understand. "Taste, clarity, craft."
