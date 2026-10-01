"""Upload the cases in eval/cases.json to LangSmith as a dataset (see design/eval-loop.md).

Running the agent on the dataset and scoring it is done by eval/run_eval.py.

From the repo root:
    python -m eval.upload_eval_cases
"""
import json

from dotenv import load_dotenv
from langsmith import Client

from src.data.order_database import REPO_ROOT

load_dotenv()

CASES_PATH = REPO_ROOT / "eval" / "cases.json"
DATASET_NAME = "refund-agent-cases"


def to_example(case: dict) -> dict:
    """One LangSmith example: the inputs go to the agent, the expected answers stay as reference outputs,
    and the metadata is for slicing results. Category, state, tier, and decision are read from the case
    data here, so they cannot disagree with it."""
    order = case["inputs"]["order"]
    return {
        "inputs": case["inputs"],
        "outputs": case["expected"],
        "metadata": {
            "case_id": case["case_id"],
            "kind": case["kind"],
            "season": case["season"],
            "category": order["item"]["category"],
            "state": order["ship_to_state"],
            "tier": order["loyalty_tier_at_purchase"],
            "decision": case["expected"]["decision"],
        },
    }


def upload_dataset(client: Client) -> None:
    if client.has_dataset(dataset_name=DATASET_NAME):
        raise SystemExit(f"Dataset {DATASET_NAME!r} already exists. Delete it in LangSmith first to re-upload.")
    cases = json.loads(CASES_PATH.read_text())
    dataset = client.create_dataset(DATASET_NAME, description="Juniper & Pine refund agent eval cases (eval/cases.json)")
    client.create_examples(dataset_id=dataset.id, examples=[to_example(case) for case in cases])
    print(f"Uploaded {len(cases)} cases to dataset {DATASET_NAME!r}.")


if __name__ == "__main__":
    upload_dataset(Client())
