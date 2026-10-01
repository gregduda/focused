"""Slice report: pass rates for one experiment, overall and grouped by slice (see design/eval-loop.md).

Reads the scores that eval/run_eval.py stored in LangSmith and the slice tags on each case. A run passes a check
when its score is 1 (gold_doc_recall passes only when every gold doc was retrieved). A check with no score for a
case (no expected deadline, no gold docs) is left out of that case's rate. With repeated runs, every run counts,
so a rate is the share of runs that passed.

By default only the development cases are shown, so the held-out cases (D-060) are not read while the agent is
being improved. Use --split all or --split holdout for the final comparison.

From the repo root:
    python -m eval.report --experiment "baseline-2026/09/30 19:50:00"
    python -m eval.report                    # the most recent experiment
    python -m eval.report --split all        # final comparison, held-out cases included
"""
import argparse
import warnings
from collections import defaultdict

from dotenv import load_dotenv
from langsmith import Client

from eval.upload_eval_cases import DATASET_NAME

load_dotenv()
warnings.simplefilter("ignore")

# key, column heading
CHECKS = [
    ("decision_correct", "decision"), ("refund_correct", "refund"), ("deadline_correct", "deadline"),
    ("escalation_correct", "escalation"), ("gold_doc_recall", "doc recall"), ("stale_doc_avoided", "no stale doc"),
    ("no_pii_leak", "no PII"), ("no_internal_disclosure", "no disclosure"), ("judge_tone", "tone"),
    ("judge_no_accusation", "no accusation"),
]
SLICES = ["split", "kind", "decision", "category", "state", "tier", "season"]
MIN_CASES = 5  # a group with fewer cases than this is marked as too small to read


def find_experiment(client: Client, name: str | None):
    experiments = list(client.list_projects(reference_dataset_name=DATASET_NAME))
    if name is None:
        return max(experiments, key=lambda p: p.start_time)
    for experiment in experiments:
        if experiment.name == name:
            return experiment
    raise SystemExit("No experiment named {!r}. Available:\n  {}".format(
        name, "\n  ".join(sorted(p.name for p in experiments))))


def load_runs(client: Client, experiment) -> list[tuple[dict, dict]]:
    """One (example metadata, {check: score}) pair per run in the experiment."""
    examples = {e.id: e for e in client.list_examples(dataset_name=DATASET_NAME)}
    pairs = []
    for run in client.list_runs(project_id=experiment.id, is_root=True):
        example = examples.get(run.reference_example_id)
        if example is not None:
            pairs.append((example.metadata, {k: v["avg"] for k, v in (run.feedback_stats or {}).items()}))
    return pairs


def rate(pairs: list[tuple[dict, dict]], key: str) -> str:
    scores = [s[key] for _, s in pairs if s.get(key) is not None]
    return f"{round(100 * sum(1 for v in scores if v == 1) / len(scores))}%" if scores else "-"


def print_table(title: str, groups: dict[str, list[tuple[dict, dict]]]) -> None:
    header = [title, "cases", "runs", *(heading for _, heading in CHECKS)]
    body = []
    for group, pairs in sorted(groups.items()):
        cases = len({m["case_id"] for m, _ in pairs})
        body.append([group + (" *" if cases < MIN_CASES else ""), str(cases), str(len(pairs)),
                     *(rate(pairs, key) for key, _ in CHECKS)])
    widths = [max(len(line[i]) for line in [header, *body]) for i in range(len(header))]
    print()
    for line in [header, ["-" * w for w in widths], *body]:
        print("  ".join(cell.ljust(width) for cell, width in zip(line, widths)))


def print_flaky(pairs: list[tuple[dict, dict]]) -> None:
    """Cases whose runs did not all agree on a check: the evidence of run-to-run variation."""
    by_case = defaultdict(list)
    for metadata, scores in pairs:
        by_case[metadata["case_id"]].append(scores)
    if max(len(runs) for runs in by_case.values()) < 2:
        return
    print("\nCases whose runs disagreed (out of {} cases)".format(len(by_case)))
    for key, heading in CHECKS:
        varied = [cid for cid, runs in by_case.items()
                  if len({s.get(key) == 1 for s in runs if s.get(key) is not None}) > 1]
        print(f"  {heading:14} {len(varied):>3}  {', '.join(sorted(varied)[:8])}{' ...' if len(varied) > 8 else ''}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", help="experiment name (default: the most recent)")
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="dev",
                        help="which cases to report (default: dev; holdout is for the final comparison only)")
    args = parser.parse_args()

    client = Client()
    experiment = find_experiment(client, args.experiment)
    pairs = [p for p in load_runs(client, experiment) if args.split == "all" or p[0]["split"] == args.split]
    cases = len({m["case_id"] for m, _ in pairs})
    print(f"Experiment {experiment.name!r}, {args.split} cases: {len(pairs)} runs over {cases} cases")

    print_table("overall", {"all": pairs})
    for slice_key in SLICES:
        if slice_key == "split" and args.split != "all":
            continue
        groups = defaultdict(list)
        for pair in pairs:
            groups[pair[0][slice_key]].append(pair)
        print_table(slice_key, groups)
    print(f"\n* fewer than {MIN_CASES} cases: too few to read as a rate")
    print_flaky(pairs)


if __name__ == "__main__":
    main()
