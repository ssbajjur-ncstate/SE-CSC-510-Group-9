import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


class PlaywrightAdapterError(ValueError):
    """
    Raised when Playwright input cannot be converted safely by TestBudget.
    """


def normalize_playwright_file(test_file):
    """
    Normalize a Playwright test file path.

    Older Playwright JUnit reports may include source location suffixes such
    as:

        tests/login.spec.ts:13:5

    TestBudget removes the unstable line and column information and stores:

        tests/login.spec.ts
    """

    if not isinstance(test_file, str) or not test_file.strip():
        raise PlaywrightAdapterError("Playwright testcase has no usable file")

    normalized = test_file.strip().replace(
        "\\",
        "/",
    )

    while normalized.startswith("./"):
        normalized = normalized[2:]

    normalized = re.sub(
        r":\d+:\d+$",
        "",
        normalized,
    )

    if not normalized:
        raise PlaywrightAdapterError("Playwright testcase has no usable file")

    return normalized


def normalize_playwright_test_id(
    test_file,
    title,
):
    """
    Build TestBudget's stable Playwright identity.

    The shared identity contract is:

        file › title
    """

    test_file = normalize_playwright_file(test_file)

    if not isinstance(title, str) or not title.strip():
        raise PlaywrightAdapterError("Playwright testcase has no title")

    return f"{test_file} › {title.strip()}"


def _element_name(element):
    """
    Return an XML element's local name without a namespace.
    """

    return element.tag.split("}")[-1]


def _children_named(
    testcase,
    names,
):
    """
    Return direct child elements whose local names match `names`.
    """

    return [child for child in testcase if _element_name(child) in names]


def _duration_from_value(
    raw_value,
    context,
):
    """
    Convert a JUnit duration to non-negative seconds.

    Missing durations are represented as 0.0.
    """

    if raw_value in (
        None,
        "",
    ):
        return 0.0

    try:
        duration = float(raw_value)

    except (
        TypeError,
        ValueError,
    ) as error:
        raise PlaywrightAdapterError(
            f"{context}: invalid JUnit time value: {raw_value}"
        ) from error

    if duration < 0:
        raise PlaywrightAdapterError(f"{context}: JUnit duration cannot be negative")

    return duration


def _parse_playwright_testcase(
    testcase,
):
    """
    Convert one Playwright JUnit testcase into one TestBudget result.

    Playwright retry metadata can appear as:

    - flakyFailure
    - flakyError
    - rerunFailure
    - rerunError

    TestBudget records only the final logical result while retaining the
    final attempt number.
    """

    test_file = testcase.attrib.get("classname")

    title = testcase.attrib.get("name")

    test_id = normalize_playwright_test_id(
        test_file,
        title,
    )

    skipped = _children_named(
        testcase,
        {"skipped"},
    )

    normal_failures = _children_named(
        testcase,
        {
            "failure",
            "error",
        },
    )

    flaky_failures = _children_named(
        testcase,
        {
            "flakyFailure",
            "flakyError",
        },
    )

    rerun_failures = _children_named(
        testcase,
        {
            "rerunFailure",
            "rerunError",
        },
    )

    if flaky_failures and rerun_failures:
        raise PlaywrightAdapterError(
            f"{test_id}: testcase contains both flaky and rerun retry metadata"
        )

    # A skipped Playwright test has no executed retry history.
    if skipped:
        return {
            "test_id": test_id,
            "status": "skipped",
            "duration_s": (
                _duration_from_value(
                    testcase.attrib.get("time"),
                    test_id,
                )
            ),
            "attempt": 1,
        }

    # Playwright includeRetries behavior:
    #
    # flakyFailure/flakyError means one or more earlier attempts failed,
    # followed by a successful final attempt. In that case Playwright's
    # testcase `time` is the passing final attempt's duration.
    if flaky_failures:
        return {
            "test_id": test_id,
            "status": "passed",
            "duration_s": (
                _duration_from_value(
                    testcase.attrib.get("time"),
                    test_id,
                )
            ),
            "attempt": (len(flaky_failures) + 1),
        }

    # A still-failing retried test has rerunFailure/rerunError children.
    #
    # Their `time` values represent subsequent retry attempts. Therefore
    # the final retry child gives us the final attempt's duration.
    if rerun_failures:
        final_retry = rerun_failures[-1]

        return {
            "test_id": test_id,
            "status": "failed",
            "duration_s": (
                _duration_from_value(
                    final_retry.attrib.get("time"),
                    test_id,
                )
            ),
            "attempt": (len(rerun_failures) + 1),
        }

    status = "failed" if normal_failures else "passed"

    return {
        "test_id": test_id,
        "status": status,
        "duration_s": (
            _duration_from_value(
                testcase.attrib.get("time"),
                test_id,
            )
        ),
        "attempt": 1,
    }


def parse_playwright_junit(
    xml_path,
):
    """
    Parse a Playwright JUnit report into deduplicated TestBudget results.

    Args:
        xml_path:
            Path to a Playwright JUnit XML report.

    Returns:
        A list of dictionaries containing:

        - test_id
        - status
        - duration_s
        - attempt

    If the same logical test appears more than once as separate testcase
    entries, TestBudget keeps the final occurrence and increments its attempt
    count. This provides compatibility with reports that encode retries as
    repeated testcase records.

    Raises:
        PlaywrightAdapterError:
            If the report is missing, malformed, or contains invalid data.
    """

    xml_path = Path(xml_path)

    if not xml_path.exists():
        raise PlaywrightAdapterError(
            f"Playwright JUnit report does not exist: {xml_path}"
        )

    try:
        tree = ET.parse(xml_path)

    except ET.ParseError as error:
        raise PlaywrightAdapterError(
            f"invalid Playwright JUnit XML: {xml_path}"
        ) from error

    root = tree.getroot()

    ordered_ids = []
    records = {}
    occurrence_counts: dict[str, int] = {}

    for testcase in root.iter("testcase"):
        record = _parse_playwright_testcase(testcase)

        test_id = record["test_id"]

        if test_id not in records:
            ordered_ids.append(test_id)

        occurrence_count = (
            occurrence_counts.get(
                test_id,
                0,
            )
            + 1
        )

        occurrence_counts[test_id] = occurrence_count

        # Internal retry information can already report attempt > 1.
        # If the JUnit producer instead repeated entire testcase entries,
        # occurrence_count provides the retry count.
        record["attempt"] = max(
            record["attempt"],
            occurrence_count,
        )

        records[test_id] = record

    return [records[test_id] for test_id in ordered_ids]


def split_playwright_test_id(
    test_id,
):
    """
    Split `file › title` into its file and title components.
    """

    if not isinstance(test_id, str) or " › " not in test_id:
        raise PlaywrightAdapterError(f"invalid Playwright test ID: {test_id}")

    test_file, title = test_id.split(
        " › ",
        1,
    )

    test_file = normalize_playwright_file(test_file)

    title = title.strip()

    if not title:
        raise PlaywrightAdapterError(f"invalid Playwright test ID: {test_id}")

    return test_file, title


def load_playwright_test_ids(
    plan_path,
):
    """
    Read Playwright test IDs selected by a TestBudget plan.

    Pytest IDs use `path::name`, while Playwright IDs use `file › title`.
    Only Playwright IDs are returned by this adapter.
    """

    plan_path = Path(plan_path)

    if not plan_path.exists():
        raise PlaywrightAdapterError(f"TestBudget plan does not exist: {plan_path}")

    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))

    except json.JSONDecodeError as error:
        raise PlaywrightAdapterError(
            f"invalid TestBudget plan JSON: {plan_path}"
        ) from error

    if not isinstance(plan, dict):
        raise PlaywrightAdapterError("TestBudget plan must be a JSON object")

    selected = plan.get("selected")

    if not isinstance(selected, list):
        raise PlaywrightAdapterError("TestBudget plan must contain a selected list")

    test_ids = []
    seen = set()

    for index, entry in enumerate(
        selected,
        start=1,
    ):
        if not isinstance(entry, dict):
            raise PlaywrightAdapterError(f"selected item {index} must be an object")

        test_id = entry.get("test_id")

        if not isinstance(test_id, str) or not test_id.strip():
            raise PlaywrightAdapterError(f"selected item {index} has no valid test_id")

        test_id = test_id.strip()

        # This adapter only owns Playwright IDs.
        if " › " not in test_id:
            continue

        # Validate the ID before returning it.
        split_playwright_test_id(test_id)

        if test_id not in seen:
            test_ids.append(test_id)

            seen.add(test_id)

    return test_ids


def build_playwright_invocations(
    plan_path,
):
    """
    Group selected Playwright tests into per-file invocations.

    Playwright does not guarantee execution ordering across files under its
    normal parallel execution model. TestBudget therefore returns one
    invocation group per file.

    File order follows the first occurrence of each file in `plan.json`.
    Test title order within each file follows the plan.

    Returns:
        A list such as:

        [
            {
                "file": "tests/checkout.spec.ts",
                "test_ids": [...],
                "titles": [...]
            }
        ]
    """

    test_ids = load_playwright_test_ids(plan_path)

    groups = {}
    file_order = []

    for test_id in test_ids:
        test_file, title = split_playwright_test_id(test_id)

        if test_file not in groups:
            groups[test_file] = {
                "file": test_file,
                "test_ids": [],
                "titles": [],
            }

            file_order.append(test_file)

        groups[test_file]["test_ids"].append(test_id)

        groups[test_file]["titles"].append(title)

    return [groups[test_file] for test_file in file_order]
