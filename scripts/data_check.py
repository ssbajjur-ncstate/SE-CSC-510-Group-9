"""Summarize available TestBudget history for the M0a data check."""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from testbudget.db import load_history_records

FIELDNAMES = [
    "category",
    "total",
    "passed",
    "failed",
    "skipped",
    "failing_runs",
    "flake_filtered_failing_runs",
    "risk_level",
    "risk_level_counts_available",
    "note",
]


def check_history(history_dir: Path) -> list[dict[str, object]]:
    """Summarize run and result counts without inventing missing metadata."""
    runs, results = load_history_records(history_dir)
    results_by_sha: dict[str, list[dict]] = defaultdict(list)

    for result in results:
        results_by_sha[result["sha"]].append(result)

    rows: list[dict[str, object]] = []

    for category, records in (
        ("runs", runs),
        ("test_results", results),
    ):
        counts = Counter(record.get("status", "recorded") for record in records)
        rows.append(
            {
                "category": category,
                "total": len(records),
                "passed": counts.get("passed", 0),
                "failed": counts.get("failed", 0),
                "skipped": counts.get("skipped", 0),
                "failing_runs": "",
                "flake_filtered_failing_runs": "",
                "risk_level": "unavailable",
                "risk_level_counts_available": False,
                "note": "",
            }
        )

    failing_runs = 0
    flake_filtered_failing_runs = 0

    for run in runs:
        run_results = results_by_sha[run["sha"]]
        failed_tests = {
            result["test_id"] for result in run_results if result["status"] == "failed"
        }

        if failed_tests:
            failing_runs += 1

        passed_tests = {
            result["test_id"] for result in run_results if result["status"] == "passed"
        }

        # A failure is treated as flaky if that test also passed
        # in another recorded attempt for the same run SHA.
        persistent_failures = failed_tests - passed_tests
        if persistent_failures:
            flake_filtered_failing_runs += 1

    no_history = not runs
    rows.append(
        {
            "category": "run_summary",
            "total": len(runs),
            "passed": "",
            "failed": "",
            "skipped": "",
            "failing_runs": failing_runs,
            "flake_filtered_failing_runs": flake_filtered_failing_runs,
            "risk_level": "unavailable",
            "risk_level_counts_available": False,
            "note": (
                "No historical runs recorded; budget decision cannot be made"
                if no_history
                else (
                    "Flake filter uses failed/passed statuses for the same test "
                    "and SHA; risk levels are not recorded in the current schema"
                )
            ),
        }
    )

    return rows


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    """Write the data-check report as CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    """Run the M0a history check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-dir", type=Path, default=Path("history"))
    parser.add_argument("--output", type=Path, default=Path("data/m0a_data_check.csv"))
    args = parser.parse_args()

    rows = check_history(args.history_dir)
    write_csv(rows, args.output)

    summary = rows[-1]
    print(f"Runs: {summary['total']}")
    print(f"Provisional failing runs: {summary['failing_runs']}")
    print(f"Flake-filtered failing runs: {summary['flake_filtered_failing_runs']}")
    print("Risk-level counts: unavailable (not recorded in current history schema)")

    if summary["total"] == 0:
        print("Decision: insufficient historical data; do not calibrate budgets.")

    print(f"CSV written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
