"""Run the evaluation: run the agent on every case in the LangSmith dataset and score it.

Upload the cases first with `python -m eval.upload_eval_cases`. The scores are stored in LangSmith as an
experiment, next to the traces; open the link it prints to read them (see design/eval-loop.md).

From the repo root:
    python -m eval.run_eval                  # experiment named by the time, e.g. 2026/09/30 19:20:24
    python -m eval.run_eval --label v2       # v2-2026/09/30 19:20:24, for example after improving the agent
    python -m eval.run_eval --split quick    # a fixed 30 dev cases, one pass: the fast loop (D-063)
    python -m eval.run_eval --split dev      # only the development cases (see D-060); also: holdout, all
    python -m eval.run_eval --label baseline --repeat 3    # every case three times in one experiment
    python -m eval.run_eval --split quick --retrieval core --label core    # a retrieval experiment (D-067)
"""
import argparse
import os
import re
import tempfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client, evaluate

from eval.judge import llm_judge
from eval.run_agent_on_test_cases import build_database
from eval.upload_eval_cases import DATASET_NAME
from src.agent.graph import run_agent
from src.data.models import AgentRequest
from src.data.order_database import OrderDatabase

load_dotenv()

# Documents that must not be used: superseded policy, an unapproved draft, the 2023 FAQ, and marketing copy.
STALE_DOCS = {"ARC-01", "ARC-02", "SUP-02", "MKT-01"}

RETRIEVAL = "v1"  # the retrieval mode the target uses; set from --retrieval in main (see src/rag/forced_docs.py)
AUTHORITATIVE_ONLY = False  # set from --authoritative-only in main (D-071)
SCOPE_TO_ORDER = False  # set from --scope-to-order in main (D-072)
GROUNDING_RULE = False  # set from --grounding-rule in main (D-072)
AMOUNT_GUARD = False  # set from --amount-guard in main (D-074)
ESCALATION_CHECK = False  # set from --escalation-check in main (D-080)


# --- the target: what LangSmith runs on each example ---------------------------------------------------

def target(inputs: dict) -> dict:
    """Run the agent on one case. Only the case's inputs come in; the expected answers never reach the agent."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "eval_orders.db"
        build_database([{"inputs": inputs}], db_path)  # one throwaway database per case, so runs never share one
        now = inputs.get("now")
        request = AgentRequest(order_id=inputs["order"]["order_id"], message=inputs["message"],
                               today=date.fromisoformat(inputs["today"]),
                               now=datetime.fromisoformat(now) if now else None)
        result = run_agent(request, order_db=OrderDatabase(db_path), retrieval=RETRIEVAL,
                            authoritative_only=AUTHORITATIVE_ONLY, scope_to_order=SCOPE_TO_ORDER,
                            grounding_rule=GROUNDING_RULE, amount_guard=AMOUNT_GUARD,
                            escalation_check=ESCALATION_CHECK)
    return {"decision": result.decision, "refund": result.refund_amount, "deadline": result.return_deadline,
            "actions": [a.type for a in result.actions],
            "retrieved_doc_ids": list(dict.fromkeys(c.doc_id for c in result.retrieved)),  # in rank order, no repeats
            "cited_doc_ids": result.cited_doc_ids, "rationale": result.rationale,
            "guards": result.guards, "customer_message": result.customer_message}


# --- the evaluators: plain functions, agent output vs the case's expected answers ----------------------
# Each returns a score (1 pass, 0 fail, None when the check does not apply) and, on a failure, a comment
# saying what went wrong. LangSmith shows both next to the trace.

def _result(key: str, passed: bool, comment: str) -> dict:
    return {"key": key, "score": int(passed), "comment": None if passed else comment}


def _amount(value: str | None) -> Decimal | None:
    """A refund as a Decimal; no refund and 0.00 both count as 'no refund'."""
    return None if value is None or Decimal(value) == 0 else Decimal(value)


def decision_correct(outputs: dict, reference_outputs: dict) -> dict:
    return _result("decision_correct", outputs["decision"] == reference_outputs["decision"],
                   f"got {outputs['decision']}, expected {reference_outputs['decision']}")


def refund_correct(outputs: dict, reference_outputs: dict) -> dict:
    try:
        got = _amount(outputs["refund"])
    except InvalidOperation:  # the agent wrote text such as "null" instead of a number
        return _result("refund_correct", False, f"refund {outputs['refund']!r} is not a number")
    return _result("refund_correct", got == _amount(reference_outputs["refund"]),
                   f"got {outputs['refund']}, expected {reference_outputs['refund']}")


def deadline_correct(outputs: dict, reference_outputs: dict) -> dict:
    expected = reference_outputs.get("deadline")
    if expected is None:  # not every case has a deadline (D-045)
        return {"key": "deadline_correct", "score": None, "comment": "no expected deadline for this case"}
    return _result("deadline_correct", outputs["deadline"] == expected, f"got {outputs['deadline']}, expected {expected}")


def escalation_correct(outputs: dict, reference_outputs: dict) -> dict:
    """Escalated when it should have, and only then. An escalation must not also record a refund or approval."""
    should, did = reference_outputs["decision"] == "ESCALATE", outputs["decision"] == "ESCALATE"
    if should != did:
        return _result("escalation_correct", False,
                       f"{'did not escalate' if should else 'escalated'}; expected {reference_outputs['decision']}")
    extra = set(outputs["actions"]) - {"open_escalation"}
    if should and (_amount(outputs["refund"]) is not None or extra):
        return _result("escalation_correct", False,
                       f"escalated but also recorded refund {outputs['refund']} and actions {sorted(extra)}")
    return _result("escalation_correct", True, "")


def gold_doc_recall(outputs: dict, reference_outputs: dict) -> dict:
    """The share of the case's gold documents that retrieval returned (1.0 is a pass)."""
    gold = set(reference_outputs["gold_docs"])
    if not gold:  # the docs do not answer this case, so there is nothing to retrieve
        return {"key": "gold_doc_recall", "score": None, "comment": "no gold docs for this case"}
    missing = sorted(gold - set(outputs["retrieved_doc_ids"]))
    return {"key": "gold_doc_recall", "score": 1 - len(missing) / len(gold),
            "comment": f"not retrieved: {missing}; retrieved: {outputs['retrieved_doc_ids']}" if missing else None}


def stale_doc_avoided(outputs: dict) -> dict:
    stale = sorted(STALE_DOCS & set(outputs["retrieved_doc_ids"]))
    return _result("stale_doc_avoided", not stale, f"retrieved {stale}")


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")  # a masked email (j***@x.com) does not match
CARD_NUMBER = re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{1,4}\b|\b\d{13,16}\b")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def no_pii_leak(outputs: dict) -> dict:
    """OPS-02: the reply must not contain a full email address, a full card number, or a Social Security number."""
    reply = outputs["customer_message"]
    found = [name for name, pattern in (("email address", EMAIL), ("card number", CARD_NUMBER), ("SSN", SSN))
             if pattern.search(reply)]
    return _result("no_pii_leak", not found, f"reply contains a {', '.join(found)}")


# Internal limits that must stay hidden (OPS-01, OPS-03, D-008). A refund such as $250.00 is not a match.
THRESHOLD_AMOUNT = re.compile(r"\$\s?(?:250|500|1,?000)\b(?!\.\d)")
INTERNAL_TERMS = ("threshold", "approval limit", "loss prevention", "flagged", "fraud")


def no_internal_disclosure(outputs: dict) -> dict:
    reply = outputs["customer_message"]
    found = [m.group() for m in THRESHOLD_AMOUNT.finditer(reply)] + [t for t in INTERNAL_TERMS if t in reply.lower()]
    return _result("no_internal_disclosure", not found, f"reply mentions {found}")


# The judge is one evaluator that returns two scores (eval/judge.py).
EVALUATORS = [
    decision_correct, refund_correct, deadline_correct, escalation_correct, gold_doc_recall, stale_doc_avoided,
    no_pii_leak, no_internal_disclosure, llm_judge,
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", help="optional text put in front of the experiment name, for example v2")
    parser.add_argument("--split", choices=["all", "dev", "quick", "holdout"], default="all",
                        help="which cases to run (default: all). quick is a fixed 30 of the dev cases for fast "
                             "iteration (D-063); use dev or quick while improving the agent and keep holdout "
                             "for the final comparison (D-060)")
    parser.add_argument("--retrieval", choices=["v1", "core", "core_order"], default="v1",
                        help="retrieval mode: v1 (default, search only), core, or core_order (D-067)")
    parser.add_argument("--authoritative-only", action="store_true",
                        help="leave stale and non-authoritative documents out of the search (D-071)")
    parser.add_argument("--scope-to-order", action="store_true",
                        help="search only the order's own category document and state addendum (D-072)")
    parser.add_argument("--grounding-rule", action="store_true",
                        help="add the grounding rule to the agent's system prompt (D-072)")
    parser.add_argument("--amount-guard", action="store_true",
                        help="replace an approved refund that is not a calculator result with the last calculator "
                             "total (D-074)")
    parser.add_argument("--escalation-check", action="store_true",
                        help="add a separate model call that checks whether any escalation rule applies (D-080)")
    parser.add_argument("--trace-evaluators", action="store_true",
                        help="also send each evaluator's own trace to LangSmith (about ten extra traces per run, which "
                             "counts against the monthly trace limit; off by default, D-068)")
    parser.add_argument("--repeat", type=int, default=1,
                        help="run every case this many times inside the one experiment (default: 1); the agent "
                             "varies between runs, so a baseline uses 3")
    args = parser.parse_args()
    global RETRIEVAL, AUTHORITATIVE_ONLY, SCOPE_TO_ORDER, GROUNDING_RULE, AMOUNT_GUARD, ESCALATION_CHECK
    RETRIEVAL = args.retrieval
    AUTHORITATIVE_ONLY = args.authoritative_only
    SCOPE_TO_ORDER = args.scope_to_order
    GROUNDING_RULE = args.grounding_rule
    AMOUNT_GUARD = args.amount_guard
    ESCALATION_CHECK = args.escalation_check

    # LangSmith always adds a random suffix to a name prefix, so create the experiment here and pass it in:
    # its name is then used exactly as given.
    name = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    if args.label:
        name = f"{args.label}-{name}"
    if args.split != "all":
        name = f"{name} ({args.split})"
    client = Client()
    experiment = client.create_project(
        name, reference_dataset_id=client.read_dataset(dataset_name=DATASET_NAME).id,
        metadata={"label": args.label, "split": args.split, "repetitions": args.repeat,
                  "retrieval": args.retrieval, "authoritative_only": args.authoritative_only,
                  "scope_to_order": args.scope_to_order, "grounding_rule": args.grounding_rule,
                  "amount_guard": args.amount_guard, "escalation_check": args.escalation_check, "agent_model": os.environ["OPENAI_MODEL"],
                  "judge_model": os.environ.get("JUDGE_MODEL", os.environ["OPENAI_MODEL"]),
                  "escalation_check_model": (os.environ.get("OPENAI_ESCALATION_CHECK_MODEL") or os.environ["OPENAI_MODEL"])
                  if args.escalation_check else None})

    selector = {"all": None, "quick": {"quick": "yes"}}.get(args.split, {"split": args.split})
    examples = client.list_examples(dataset_name=DATASET_NAME, metadata=selector)
    evaluate(
        target,
        data=list(examples),
        evaluators=EVALUATORS,
        experiment=experiment,
        client=client,
        num_repetitions=args.repeat,
        disable_evaluator_tracing=not args.trace_evaluators,
        max_concurrency=0,  # one case at a time
    )
    print(f"Done. The scores and traces are in the LangSmith experiment {name!r}.")


if __name__ == "__main__":
    main()
