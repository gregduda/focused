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
            "split": case["split"],
            "category": order["item"]["category"],
            "state": order["ship_to_state"],
            "tier": order["loyalty_tier_at_purchase"],
            "decision": case["expected"]["decision"],
        },
    }


def upload_dataset(client: Client) -> None:
    """Make the LangSmith dataset match eval/cases.json: create it, add new cases, and update changed ones.
    Cases are matched by case_id. Nothing is deleted, so earlier experiments stay linked to their examples.
    A case removed from cases.json has to be deleted in LangSmith by hand."""
    cases = json.loads(CASES_PATH.read_text())
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
    else:
        dataset = client.create_dataset(
            DATASET_NAME, description="Juniper & Pine refund agent eval cases (eval/cases.json)")
    existing = {e.metadata["case_id"]: e for e in client.list_examples(dataset_id=dataset.id)}

    to_add, to_update = [], []
    for case in cases:
        example = to_example(case)
        old = existing.get(case["case_id"])
        if old is None:
            to_add.append(example)
        elif (old.inputs, old.outputs) != (example["inputs"], example["outputs"]) or any(
                old.metadata.get(k) != v for k, v in example["metadata"].items()):
            client.update_example(old.id, inputs=example["inputs"], outputs=example["outputs"],
                                  metadata={**old.metadata, **example["metadata"]})
            to_update.append(case["case_id"])
    if to_add:
        client.create_examples(dataset_id=dataset.id, examples=to_add)
    unchanged = len(cases) - len(to_add) - len(to_update)
    print(f"Dataset {DATASET_NAME!r}: {len(to_add)} added, {len(to_update)} updated, {unchanged} unchanged.")


if __name__ == "__main__":
    upload_dataset(Client())
