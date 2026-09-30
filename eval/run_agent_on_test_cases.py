"""Run the eval cases through the agent and print what the agent produced for each one.

This only runs the agent. It never reads a case's expected answers; comparing output to them is the
evaluators' job (see design/eval-loop.md).
The customers and orders in eval/cases.json are written into a throwaway SQLite database, built from
data/schema.sql, so the cases do not depend on data/seed.sql. Each case's `today` is passed to the agent.

From the repo root:
    python -m eval.run_agent_on_test_cases                 # every case
    python -m eval.run_agent_on_test_cases --case A4       # one case
"""
import argparse
import asyncio
import itertools
import json
import sqlite3
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tracers.context import collect_runs
from langchain_core.tracers.langchain import wait_for_all_tracers
from langsmith import Client

from src.agent.graph import run_agent
from src.data.models import AgentRequest
from src.data.order_database import REPO_ROOT, OrderDatabase

load_dotenv()

CASES_PATH = REPO_ROOT / "eval" / "cases.json"
SCHEMA_PATH = REPO_ROOT / "data" / "schema.sql"
SEPARATOR = "=" * 80
BLOCK_RULE = "~" * 80


@contextmanager
def spinner(message: str):
    """Show a spinning character next to `message` while the block runs, then a check mark."""
    done = threading.Event()

    def spin() -> None:
        for frame in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
            if done.is_set():
                break
            print(f"\r{frame} {message}", end="", flush=True)
            time.sleep(0.1)

    thread = threading.Thread(target=spin)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join()
        print(f"\r✓ {message}")


def build_database(cases: list[dict], db_path: Path) -> None:
    """Create the order database from schema.sql and insert every case's customer, order, and item."""
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text())
    for case in cases:
        customer, order = case["inputs"]["customer"], case["inputs"]["order"]
        item = order["item"]
        conn.execute("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", (
            customer["customer_id"], customer["first_name"], customer["last_name"], customer["email"],
            customer["loyalty_tier_current"], customer["returns_last_60d"], customer["refunded_last_60d"],
            customer["last_keep_it_refund_date"]))
        conn.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", (
            order["order_id"], customer["customer_id"], order["order_date"], order["status"], order["delivered_date"],
            order["estimated_delivery_date"], order["ship_to_state"], order["loyalty_tier_at_purchase"],
            order["outbound_shipping_paid"]))
        conn.execute("INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            item["item_id"], order["order_id"], item["name"], item["category"], item["price_paid"], item["tax"],
            item.get("is_set", 0), ",".join(item.get("tags", [])), item.get("final_sale_flag", 0),
            item.get("final_sale_on_confirmation", 0), item.get("is_oversized", 0)))
    conn.commit()
    conn.close()


def print_block(label: str, text: str) -> None:
    """Print multi-line text between ~~~ lines so it is easy to see where it starts and ends."""
    print(f"\n{label.capitalize()}:\n{BLOCK_RULE}\n{text}\n{BLOCK_RULE}\n")


def trace_url(run) -> str:
    """The LangSmith link for a finished run. The run object does not carry the project id, so look it up."""
    client = Client()
    project_id = str(client.read_project(project_name=run.session_name).id)
    link = asyncio.run(client.runs.get_url(
        str(run.id), project_id=project_id, trace_id=str(run.trace_id), start_time=run.start_time.isoformat()))
    return link.url


def run_case(case: dict, order_db: OrderDatabase) -> None:
    inputs = case["inputs"]  # only the inputs go to the agent; the expected answers are for the evaluators
    now = inputs.get("now")
    request = AgentRequest(order_id=inputs["order"]["order_id"], message=inputs["message"],
                           today=date.fromisoformat(inputs["today"]), now=datetime.fromisoformat(now) if now else None)
    print(f"\n{SEPARATOR}")
    print(f"{case['case_id']} | case type: {case['kind']} | today {inputs['today']}")
    print_block("message", inputs["message"])
    with collect_runs() as runs, spinner(f"Running agent on {case['case_id']}"):
        result = run_agent(request, order_db=order_db)
    print(f"decision: {result.decision}")
    print(f"refund:   {result.refund_amount}")
    print(f"deadline: {result.return_deadline}")
    print(f"docs:     {result.cited_doc_ids}")
    print_block("reply", result.customer_message)
    wait_for_all_tracers()
    time.sleep(2)  # let LangSmith finish ingesting before asking for the link
    try:
        print(f"trace:    {trace_url(runs.traced_runs[0])}")
    except Exception as error:  # a missing link should not hide the result
        print(f"trace:    (link unavailable: {error})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", help="run only this case_id (default: all)")
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text())
    selected = [c for c in cases if args.case in (None, c["case_id"])]
    if not selected:
        parser.error(f"no case with case_id {args.case!r}")

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "eval_orders.db"
        with spinner("Building temporary order database"):
            build_database(cases, db_path)
            order_db = OrderDatabase(db_path)
        for case in selected:
            run_case(case, order_db)


if __name__ == "__main__":
    main()
