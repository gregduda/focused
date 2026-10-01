"""Run the evaluation: run the agent on every case in the LangSmith dataset, score it, and print a table.

Upload the cases first with `python -m eval.upload_eval_cases`. The scores are stored in LangSmith as an
experiment, next to the traces, and the same scores are printed here (see design/eval-loop.md).

From the repo root:
    python -m eval.run_eval                  # experiment named by the time, e.g. 2026/09/30 19:20:24
    python -m eval.run_eval --label v2       # v2-2026/09/30 19:20:24, for example after improving the agent
"""
import argparse
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client, evaluate

from eval.run_agent_on_test_cases import build_database
from eval.upload_eval_cases import DATASET_NAME
from src.agent.graph import run_agent
from src.data.models import AgentRequest
from src.data.order_database import OrderDatabase

load_dotenv()


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
        result = run_agent(request, order_db=OrderDatabase(db_path))
    return {"decision": result.decision, "refund": result.refund_amount, "deadline": result.return_deadline,
            "cited_doc_ids": result.cited_doc_ids, "rationale": result.rationale,
            "customer_message": result.customer_message}


# --- the evaluators: plain functions, agent output vs the case's expected answers ----------------------

def _amount(value: str | None) -> Decimal | None:
    """A refund as a Decimal; no refund and 0.00 both count as 'no refund'."""
    return None if value is None or Decimal(value) == 0 else Decimal(value)


def decision_correct(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "decision_correct", "score": int(outputs["decision"] == reference_outputs["decision"])}


def refund_correct(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "refund_correct", "score": int(_amount(outputs["refund"]) == _amount(reference_outputs["refund"]))}


def deadline_correct(outputs: dict, reference_outputs: dict) -> dict:
    expected = reference_outputs.get("deadline")
    if expected is None:  # not every case has a deadline (D-045)
        return {"key": "deadline_correct", "score": None, "comment": "no expected deadline for this case"}
    return {"key": "deadline_correct", "score": int(outputs["deadline"] == expected)}


# key, evaluator, which agent output it looks at, which expected answer it compares with
CHECKS = [
    ("decision_correct", decision_correct, "decision", "decision"),
    ("refund_correct", refund_correct, "refund", "refund"),
    ("deadline_correct", deadline_correct, "deadline", "deadline"),
]


# --- the table -----------------------------------------------------------------------------------------

def _scores(row: dict) -> dict:
    return {r.key: r.score for r in row["evaluation_results"]["results"]}


def _cell(score: int | None, got, expected) -> str:
    if score is None:
        return f"- {got}"
    return f"✓ {got}" if score else f"✗ {got} (expected {expected})"


def print_table(rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: r["example"].metadata["case_id"])
    header = ["case", "type", *(key.removesuffix("_correct") for key, *_ in CHECKS)]
    body = []
    for row in rows:
        scores, got, expected = _scores(row), row["run"].outputs or {}, row["example"].outputs
        body.append([row["example"].metadata["case_id"], row["example"].metadata["kind"],
                     *(_cell(scores.get(key), got.get(out_key), expected.get(exp_key))
                       for key, _, out_key, exp_key in CHECKS)])
    widths = [max(len(line[i]) for line in [header, *body]) for i in range(len(header))]
    for line in [header, ["-" * w for w in widths], *body]:
        print("  ".join(cell.ljust(width) for cell, width in zip(line, widths)))
    print()
    for key, *_ in CHECKS:
        scored = [s for s in (_scores(row).get(key) for row in rows) if s is not None]
        print(f"{key}: {sum(scored)} of {len(scored)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", help="optional text put in front of the experiment name, for example v2")
    args = parser.parse_args()

    # LangSmith always adds a random suffix to a name prefix, so create the experiment here and pass it in:
    # its name is then used exactly as given.
    name = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    if args.label:
        name = f"{args.label}-{name}"
    client = Client()
    experiment = client.create_project(name, reference_dataset_id=client.read_dataset(dataset_name=DATASET_NAME).id)

    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[evaluator for _, evaluator, *_ in CHECKS],
        experiment=experiment,
        client=client,
        max_concurrency=0,  # one case at a time
    )
    print_table(list(results))


if __name__ == "__main__":
    main()
