import argparse
from pathlib import Path

from testbudget.db import (
    get_test_stats,
    init_db,
    insert_test_results,
)
from testbudget.ingest import parse_junit

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
        from testbudget.selector import select_with_budget
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
        plan = select_with_budget(
            ranked,
            args.budget,
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    print_plan(
        changed_files=args.changed,
        ranked_tests=ranked,
        plan=plan,
    )

    return 0


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


def handle_links(args):
   from testbudget.links.report import (
       format_report,
       read_links_file,
       summarize_links,
   )

   if not args.report:
       print("Nothing to do. Use --report.")
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
