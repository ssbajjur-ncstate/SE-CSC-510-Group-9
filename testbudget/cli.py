import argparse
from pathlib import Path

import yaml

from testbudget.db import (
    HistoryFormatError,
    get_test_stats,
    init_db,
    insert_test_results,
    load_history_records,
)
from testbudget.ingest import parse_junit
from testbudget.plan import build_plan, plan_risk_level, write_plan
from testbudget.rules import RuleContext

DEFAULT_DB = "testbudget.db"
DEFAULT_LINKS = "fixtures/test_links.json"


def build_parser():
    parser = argparse.ArgumentParser(
        prog="testbudget",
        description=(
            "Plan which tests should run within a pull-request execution budget."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize the local TestBudget database.",
    )
    init_parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help=f"SQLite database path (default: {DEFAULT_DB})",
    )
    init_parser.set_defaults(handler=handle_init)

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Import a JUnit XML test report into TestBudget history.",
    )
    ingest_parser.add_argument(
        "xml_path",
        help="Path to the JUnit XML report.",
    )
    ingest_parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help=f"SQLite database path (default: {DEFAULT_DB})",
    )
    ingest_parser.add_argument(
        "--changed-file",
        default=None,
        help=("Optional source file associated with this historical run."),
    )
    ingest_parser.set_defaults(handler=handle_ingest)

    plan_parser = subparsers.add_parser(
        "plan",
        help="Rank tests and select those that fit the supplied budget.",
    )
    plan_parser.add_argument(
        "--changed",
        action="append",
        required=True,
        help=("Changed source file. Repeat --changed for multiple files."),
    )
    plan_parser.add_argument(
        "--budget",
        type=float,
        required=True,
        help="Maximum execution-time budget in seconds.",
    )
    plan_parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help=f"SQLite database path (default: {DEFAULT_DB})",
    )
    plan_parser.add_argument(
        "--links",
        default=DEFAULT_LINKS,
        help=f"Test-link fixture path (default: {DEFAULT_LINKS})",
    )
    plan_parser.add_argument(
        "--config",
        default="testbudget.yml",
        help="TestBudget config with pins and rotation limit (default: testbudget.yml)",
    )
    plan_parser.add_argument(
        "--history",
        default="history",
        help="Directory with runs.jsonl and results.jsonl (default: history)",
    )
    plan_parser.add_argument(
        "--output",
        help="Write plan.json in the shared plan contract to this path.",
    )
    plan_parser.add_argument(
        "--sha",
        default="HEAD",
        help="Commit SHA recorded in plan.json (default: HEAD)",
    )
    plan_parser.set_defaults(handler=handle_plan)

    links_parser = subparsers.add_parser(
        "links",
        help="Inspect the link map between tests and source files.",
    )
    links_parser.add_argument(
        "--report",
        action="store_true",
        help="Print a summary of the links file.",
    )
    links_parser.add_argument(
        "--build",
        action="store_true",
        help="Build links.json from imports, routes, co-failures and pins.",
    )
    links_parser.add_argument(
        "--output",
        default="links.json",
        help="Where --build writes the links file (default: links.json)",
    )
    links_parser.add_argument(
        "--root",
        default=".",
        help="Repository root scanned by --build (default: .)",
    )
    links_parser.add_argument(
        "--history",
        default="history",
        help="JSONL history dir for co-failure links (default: history)",
    )
    links_parser.add_argument(
        "--config",
        default="testbudget.yml",
        help="Config with pins for pin links (default: testbudget.yml)",
    )
    links_parser.add_argument(
        "--links",
        default=DEFAULT_LINKS,
        help=f"Path to the links file (default: {DEFAULT_LINKS})",
    )
    links_parser.set_defaults(handler=handle_links)

    return parser


def handle_init(args):
    init_db(args.db)

    print("Initialized TestBudget")
    print(f"Database: {args.db}")

    return 0


def handle_ingest(args):
    xml_path = Path(args.xml_path)

    if not xml_path.exists():
        print(f"JUnit file not found: {args.xml_path}")
        return 1

    results = parse_junit(xml_path)

    inserted = insert_test_results(
        args.db,
        results,
        changed_file=args.changed_file,
    )

    passed = sum(1 for result in results if result["status"] == "passed")
    failed = sum(1 for result in results if result["status"] == "failed")
    skipped = sum(1 for result in results if result["status"] == "skipped")

    print("Imported CI history")
    print(f"Results: {inserted}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"Database: {args.db}")

    return 0


def handle_plan(args):
    # Member 2 may still be working when this file is first written.
    # Lazy imports allow init/ingest to work before M2 is merged.
    try:
        from testbudget.ranker import load_links, rank_tests
        from testbudget.selector import select_with_rules
    except ImportError:
        print("Ranking subsystem is not available yet. Merge M2 before running plan.")
        return 1

    if args.budget < 0:
        print("Budget cannot be negative")
        return 1

    links_path = Path(args.links)

    if not links_path.exists():
        print(f"Test-link file not found: {args.links}")
        return 1

    stats = get_test_stats(args.db)

    if not stats:
        print("No test history found. Run the ingest command before creating a plan.")
        return 1

    links = load_links(links_path)

    ranked = rank_tests(
        stats,
        args.changed,
        links,
    )

    try:
        config = _load_config(args.config)
        runs, results = _load_history(args.history)
        context = RuleContext(
            config=config,
            changed_files=args.changed,
            runs=runs,
            results=results,
        )
        plan = select_with_rules(ranked, args.budget, context)
    except (ValueError, TypeError, HistoryFormatError) as exc:
        print(str(exc))
        return 1

    if args.output:
        risk = plan_risk_level(args.changed, runs, results)
        write_plan(build_plan(args.sha, plan, risk, args.budget), args.output)

    print_plan(
        changed_files=args.changed,
        ranked_tests=ranked,
        plan=plan,
    )
    if args.output:
        print(f"Plan written: {args.output}")

    return 0


def _load_config(path):
    """Return the parsed config at ``path``, or {} if it does not exist."""
    config_path = Path(path)
    if not config_path.exists():
        return {}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def _load_history(path):
    """Return ``(runs, results)`` from a JSONL history dir, or empty lists."""
    if not (Path(path) / "runs.jsonl").exists():
        return [], []
    return load_history_records(path)


def print_plan(changed_files, ranked_tests, plan):
    print("TESTBUDGET PLAN")
    print("-" * 48)

    print("Changed files:")
    for changed_file in changed_files:
        print(f"  {changed_file}")

    print()
    print(f"Budget: {plan['budget']:.1f} sec")

    print()
    print("RANKED TESTS")

    for index, test in enumerate(ranked_tests, start=1):
        print(
            f"{index}. {test['test_name']} | "
            f"score={test['score']:.3f} | "
            f"runtime={test['duration']:.2f}s | "
            f"{test['reason']}"
        )

    print()
    print("SELECTED")

    if plan["selected"]:
        for test in plan["selected"]:
            print(f"  + {test['test_name']} ({test['duration']:.2f}s)")
    else:
        print("  None")

    print()
    print("SKIPPED")

    if plan["skipped"]:
        for test in plan["skipped"]:
            print(
                f"  - {test['test_name']} "
                f"({test['duration']:.2f}s) - "
                f"{test.get('skip_reason', 'not selected')}"
            )
    else:
        print("  None")

    print()
    print(
        f"Estimated runtime: {plan['estimated_runtime']:.2f} / {plan['budget']:.2f} sec"
    )


def build_links(root, history_dir, config_path):
    """
    Build the merged link map from every link source.

    Args:
        root: Repository root scanned for Python imports and Next.js routes.
        history_dir: JSONL history directory for co-failure links; skipped
            if it has no runs.jsonl.
        config_path: ``testbudget.yml`` with pins; skipped if missing.
    Returns:
        ``{test_id: [{file, source, weight}]}`` merged across sources.
    Raises:
        ValueError: If the config or history is malformed.
    """
    from testbudget.links.cofail import build_cofail_links
    from testbudget.links.imports import build_import_links
    from testbudget.links.pins import build_pin_links
    from testbudget.links.routes import build_route_links
    from testbudget.links.writer import merge_links

    root_path = Path(root)
    sources = [build_import_links(root_path), build_route_links(root_path)[0]]
    runs, results = _load_history(history_dir)
    sources.append(build_cofail_links(list(runs), list(results)))
    if Path(config_path).exists():
        sources.append(build_pin_links(config_path))
    return merge_links(*sources)


def handle_links(args):
    from testbudget.links.report import (
        format_report,
        read_links_file,
        summarize_links,
    )

    if args.build:
        try:
            links = build_links(args.root, args.history, args.config)
        except (ValueError, HistoryFormatError) as exc:
            print(str(exc))
            return 1
        from testbudget.links.writer import write_links

        write_links(links, args.output)
        print(f"Links written: {args.output} ({len(links)} tests)")
        if not args.report:
            return 0
        args.links = args.output

    if not args.report:
        print("Nothing to do. Use --report or --build.")
        return 1

    try:
        links = read_links_file(args.links)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc))
        return 1

    print(format_report(summarize_links(links)))

    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
