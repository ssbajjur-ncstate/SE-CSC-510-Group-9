"""Temporal replay evaluation for TestBudget.

The evaluator replays historical runs in timestamp order.  The plan for run N
is built only from runs that happened before N, preventing future information
from leaking into the ranking.

The module compares TestBudget with the baselines documented in
docs/eval-protocol.md and evaluates all methods at 30% of full-suite runtime.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Callable

from testbudget.baselines import BASELINES
from testbudget.ranker import rank_tests


BUDGET_FRACTION = 0.30
MIN_FAILING_RUNS = 10
RANDOM_SEEDS = (0, 1, 2, 3, 4)


def read_jsonl(path: str | Path) -> list[dict]:
    """Read a JSONL file, ignoring blank lines."""

    path = Path(path)

    if not path.exists():
        return []

    rows = []

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSON"
                ) from error

            if not isinstance(row, dict):
                raise ValueError(
                    f"{path}:{line_number}: expected a JSON object"
                )

            rows.append(row)

    return rows


def _results_by_sha(results: list[dict]) -> dict[str, list[dict]]:
    """Group raw history result rows by commit SHA."""

    grouped: dict[str, list[dict]] = defaultdict(list)

    for result in results:
        grouped[result["sha"]].append(result)

    return grouped


def _dedupe_attempts(results: list[dict]) -> list[dict]:
    """Return one logical result per test.

    A test that passes on any attempt on the same SHA is treated as passing for
    failure-evaluation purposes.  Otherwise the final attempt is retained.
    """

    by_test: dict[str, list[dict]] = defaultdict(list)
    order: list[str] = []

    for result in results:
        test_id = result["test_id"]

        if test_id not in by_test:
            order.append(test_id)

        by_test[test_id].append(result)

    normalized = []

    for test_id in order:
        attempts = sorted(
            by_test[test_id],
            key=lambda row: int(row.get("attempt", 1)),
        )

        final = dict(attempts[-1])

        if any(row["status"] == "passed" for row in attempts):
            final["status"] = "passed"

        normalized.append(final)

    return normalized


def _test_file(test_id: str) -> str:
    """Return the file part of a normalized pytest or Playwright test ID."""

    if "::" in test_id:
        return test_id.split("::", 1)[0]

    if " › " in test_id:
        return test_id.split(" › ", 1)[0]

    return test_id


def build_stats(
    prior_runs: list[dict],
    prior_results: list[dict],
) -> list[dict]:
    """Build ranking statistics using only previously observed runs."""

    runs_by_sha = {
        run["sha"]: run
        for run in prior_runs
    }

    grouped = _results_by_sha(prior_results)

    stats: dict[str, dict] = {}

    for sha, raw_results in grouped.items():
        run = runs_by_sha.get(sha)

        if run is None:
            continue

        timestamp = run["timestamp"]
        changed_files = set(run.get("changed_files", []))

        for result in _dedupe_attempts(raw_results):
            test_id = result["test_id"]

            entry = stats.setdefault(
                test_id,
                {
                    "test_name": test_id,
                    "run_count": 0,
                    "failure_count": 0,
                    "durations": [],
                    "last_failed_at": None,
                    "last_modified_at": None,
                },
            )

            entry["run_count"] += 1
            entry["durations"].append(
                float(result.get("duration_s", 0.0))
            )

            if result["status"] == "failed":
                entry["failure_count"] += 1
                entry["last_failed_at"] = timestamp

            if _test_file(test_id) in changed_files:
                entry["last_modified_at"] = timestamp

    answer = []

    for test_id in sorted(stats):
        entry = stats[test_id]
        durations = entry.pop("durations")

        entry["avg_duration"] = (
            sum(durations) / len(durations)
            if durations
            else 0.0
        )

        answer.append(entry)

    return answer


def load_links(path: str | Path | None) -> dict[str, list[str]]:
    """Load links and normalize them to changed-file -> test IDs."""

    if path is None:
        return {}

    path = Path(path)

    if not path.exists():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        return {}

    # Older ranker-style fixture:
    # {"src/a.py": ["tests/test_a.py::test_a"]}
    if all(
        isinstance(value, list)
        and all(isinstance(item, str) for item in value)
        for value in raw.values()
    ):
        return raw

    # Shared links contract:
    # {test_id: [{file, source, weight}, ...]}
    reversed_links: dict[str, list[str]] = defaultdict(list)

    for test_id, link_rows in raw.items():
        if not isinstance(link_rows, list):
            continue

        for link in link_rows:
            if not isinstance(link, dict):
                continue

            changed_file = link.get("file")

            if changed_file:
                reversed_links[changed_file].append(test_id)

    return dict(reversed_links)


def _current_suite(results: list[dict]) -> list[str]:
    """Return current suite order with retries removed."""

    return [
        row["test_id"]
        for row in _dedupe_attempts(results)
    ]


def _duration_map(results: list[dict]) -> dict[str, float]:
    """Return current-run duration for each logical test."""

    return {
        row["test_id"]: float(row.get("duration_s", 0.0))
        for row in _dedupe_attempts(results)
    }


def _complete_order(
    ranked_names: list[str],
    current_suite: list[str],
) -> list[str]:
    """Restrict ranking to current suite and append unseen tests."""

    current = set(current_suite)

    answer = [
        name
        for name in ranked_names
        if name in current
    ]

    seen = set(answer)

    answer.extend(
        name
        for name in current_suite
        if name not in seen
    )

    return answer


def _select_under_budget(
    order: list[str],
    durations: dict[str, float],
    budget_s: float,
) -> list[str]:
    """Greedily select ordered tests without exceeding the budget."""

    selected = []
    used = 0.0

    for test_id in order:
        duration = durations.get(test_id, 0.0)

        if used + duration <= budget_s + 1e-12:
            selected.append(test_id)
            used += duration

    return selected


def _time_to_first_failure(
    order: list[str],
    durations: dict[str, float],
    failures: set[str],
) -> float | None:
    """Return cumulative runtime through the first failing test."""

    elapsed = 0.0

    for test_id in order:
        elapsed += durations.get(test_id, 0.0)

        if test_id in failures:
            return elapsed

    return None


def _apfdc(
    order: list[str],
    durations: dict[str, float],
    failures: set[str],
) -> float:
    """Compute cost-aware fault-detection score for the observed failures."""

    if not failures:
        return 1.0

    total_cost = sum(
        durations.get(test_id, 0.0)
        for test_id in order
    )

    if total_cost <= 0:
        return 1.0

    positions = {
        test_id: index
        for index, test_id in enumerate(order)
    }

    scores = []

    for failing_test in failures:
        if failing_test not in positions:
            scores.append(0.0)
            continue

        index = positions[failing_test]

        cost_before = sum(
            durations.get(test_id, 0.0)
            for test_id in order[:index]
        )

        own_cost = durations.get(failing_test, 0.0)

        score = 1.0 - (
            cost_before + 0.5 * own_cost
        ) / total_cost

        scores.append(max(0.0, min(1.0, score)))

    return sum(scores) / len(scores)


def _ranked_names(ranked: list[dict]) -> list[str]:
    """Extract normalized test names from a ranker result."""

    return [
        row["test_name"]
        for row in ranked
    ]


def replay_details(
    runs: list[dict],
    results: list[dict],
    links: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Replay all historically failing runs with a strict temporal split."""

    links = links or {}

    runs = sorted(
        runs,
        key=lambda row: (
            row["timestamp"],
            row["sha"],
        ),
    )

    by_sha = _results_by_sha(results)

    prior_runs: list[dict] = []
    prior_results: list[dict] = []

    details = []

    for run_index, run in enumerate(runs):
        sha = run["sha"]
        current_raw = by_sha.get(sha, [])
        current = _dedupe_attempts(current_raw)

        failures = {
            row["test_id"]
            for row in current
            if row["status"] == "failed"
        }

        suite = _current_suite(current_raw)
        durations = _duration_map(current_raw)

        if failures and suite:
            stats = build_stats(
                prior_runs,
                prior_results,
            )

            changed_files = run.get(
                "changed_files",
                [],
            )

            full_runtime = sum(durations.values())
            budget_s = full_runtime * BUDGET_FRACTION

            rankings: dict[str, list[str]] = {}

            testbudget_ranked = rank_tests(
                stats,
                changed_files,
                links,
            )

            rankings["testbudget"] = _complete_order(
                _ranked_names(testbudget_ranked),
                suite,
            )

            rankings["original"] = list(suite)

            for name, ranker in BASELINES.items():
                ranked = ranker(
                    stats,
                    changed_files,
                    links,
                )

                rankings[name] = _complete_order(
                    _ranked_names(ranked),
                    suite,
                )

            # Deterministic random baseline averaged across several seeds.
            random_orders = []

            for seed in RANDOM_SEEDS:
                order = list(suite)
                random.Random(
                    seed + run_index * 1000
                ).shuffle(order)
                random_orders.append(order)

            for method, order in rankings.items():
                selected = _select_under_budget(
                    order,
                    durations,
                    budget_s,
                )

                details.append(
                    {
                        "sha": sha,
                        "method": method,
                        "history_runs_used": len(prior_runs),
                        "budget_fraction": BUDGET_FRACTION,
                        "caught": bool(
                            failures.intersection(selected)
                        ),
                        "apfdc": _apfdc(
                            order,
                            durations,
                            failures,
                        ),
                        "time_to_first_failure_s":
                            _time_to_first_failure(
                                order,
                                durations,
                                failures,
                            ),
                    }
                )

            random_caught = []
            random_apfdc = []
            random_ttff = []

            for order in random_orders:
                selected = _select_under_budget(
                    order,
                    durations,
                    budget_s,
                )

                random_caught.append(
                    1.0
                    if failures.intersection(selected)
                    else 0.0
                )

                random_apfdc.append(
                    _apfdc(
                        order,
                        durations,
                        failures,
                    )
                )

                ttff = _time_to_first_failure(
                    order,
                    durations,
                    failures,
                )

                if ttff is not None:
                    random_ttff.append(ttff)

            details.append(
                {
                    "sha": sha,
                    "method": "random",
                    "history_runs_used": len(prior_runs),
                    "budget_fraction": BUDGET_FRACTION,
                    "caught": sum(random_caught)
                    / len(random_caught),
                    "apfdc": sum(random_apfdc)
                    / len(random_apfdc),
                    "time_to_first_failure_s":
                        statistics.median(random_ttff)
                        if random_ttff
                        else None,
                }
            )

        prior_runs.append(run)
        prior_results.extend(current_raw)

    return details


def summarize(details: list[dict]) -> list[dict]:
    """Aggregate per-run replay records by evaluation method."""

    grouped: dict[str, list[dict]] = defaultdict(list)

    for row in details:
        grouped[row["method"]].append(row)

    rows = []

    for method in sorted(grouped):
        method_rows = grouped[method]

        failing_runs = len(method_rows)

        caught_runs = sum(
            float(row["caught"])
            for row in method_rows
        )

        catch_rate = (
            caught_runs / failing_runs
            if failing_runs
            else 0.0
        )

        apfdc = statistics.mean(
            row["apfdc"]
            for row in method_rows
        )

        ttff_values = [
            row["time_to_first_failure_s"]
            for row in method_rows
            if row["time_to_first_failure_s"]
            is not None
        ]

        rows.append(
            {
                "method": method,
                "risk_level": "global",
                "budget_fraction": BUDGET_FRACTION,
                "failing_runs": failing_runs,
                "caught_runs": round(
                    caught_runs,
                    3,
                ),
                "catch_rate": round(
                    catch_rate,
                    3,
                ),
                "mean_apfdc": round(
                    apfdc,
                    3,
                ),
                "median_time_to_first_failure_s":
                    round(
                        statistics.median(ttff_values),
                        3,
                    )
                    if ttff_values
                    else "",
                "data_quality":
                    "sufficient"
                    if failing_runs
                    >= MIN_FAILING_RUNS
                    else (
                        "insufficient: fewer than "
                        f"{MIN_FAILING_RUNS} failing runs"
                    ),
            }
        )

    return rows


def write_results(
    rows: list[dict],
    output: str | Path,
) -> None:
    """Write aggregated evaluation results as CSV."""

    output = Path(output)
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "method",
        "risk_level",
        "budget_fraction",
        "failing_runs",
        "caught_runs",
        "catch_rate",
        "mean_apfdc",
        "median_time_to_first_failure_s",
        "data_quality",
    ]

    with output.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def run_evaluation(
    history_dir: str | Path,
    output: str | Path,
    links_path: str | Path | None = None,
) -> list[dict]:
    """Run temporal replay from a committed history directory."""

    history_dir = Path(history_dir)

    runs = read_jsonl(
        history_dir / "runs.jsonl"
    )

    results = read_jsonl(
        history_dir / "results.jsonl"
    )

    links = load_links(links_path)

    details = replay_details(
        runs,
        results,
        links,
    )

    rows = summarize(details)
    write_results(rows, output)

    return rows


def main() -> int:
    """CLI entry point for replay evaluation."""

    parser = argparse.ArgumentParser(
        description=(
            "Replay TestBudget history using a strict "
            "temporal split."
        )
    )

    parser.add_argument(
        "--history",
        default="fixtures/history_small",
        help=(
            "Directory containing runs.jsonl "
            "and results.jsonl."
        ),
    )

    parser.add_argument(
        "--links",
        default=None,
        help="Optional links.json file.",
    )

    parser.add_argument(
        "--output",
        default="data/eval_results.csv",
        help="Evaluation CSV destination.",
    )

    args = parser.parse_args()

    rows = run_evaluation(
        args.history,
        args.output,
        args.links,
    )

    if not rows:
        print(
            "M0 replay produced no failing runs."
        )
        return 0

    print(
        "M0 temporal replay at "
        f"{BUDGET_FRACTION:.0%} of suite time"
    )

    print()

    for row in rows:
        print(
            f"{row['method']}: "
            f"catch_rate={row['catch_rate']:.3f}, "
            f"APFDc={row['mean_apfdc']:.3f}, "
            "median_time_to_first_failure="
            f"{row['median_time_to_first_failure_s']}, "
            f"failing_runs={row['failing_runs']}"
        )

    failing_runs = max(
        row["failing_runs"]
        for row in rows
    )

    print()

    if failing_runs < MIN_FAILING_RUNS:
        print(
            "M0 RESULT: INSUFFICIENT DATA — "
            f"only {failing_runs} failing historical "
            f"runs are available; at least "
            f"{MIN_FAILING_RUNS} are required "
            "for the project claim."
        )
    else:
        testbudget = next(
            row
            for row in rows
            if row["method"] == "testbudget"
        )

        best_baseline = max(
            row["catch_rate"]
            for row in rows
            if row["method"] != "testbudget"
        )

        if (
            testbudget["catch_rate"] >= 0.85
            and testbudget["catch_rate"]
            > best_baseline
        ):
            print(
                "M0 RESULT: HYPOTHESIS SUPPORTED"
            )
        else:
            print(
                "M0 RESULT: HYPOTHESIS NOT SUPPORTED"
            )

    print(
        f"Results written to {args.output}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())