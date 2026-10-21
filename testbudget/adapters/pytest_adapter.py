import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


class PytestAdapterError(ValueError):
    """
    Raised when pytest input cannot be converted safely by TestBudget.
    """


def _normalize_path(path):
    """
    Normalize a test file path into TestBudget's forward-slash form.
    """

    path = str(path).strip()

    path = path.replace(
        "\\",
        "/",
    )

    while path.startswith("./"):
        path = path[2:]

    return path


def _file_from_classname(classname):
    """
    Infer a pytest file path from a JUnit classname.

    Examples:

        tests.test_checkout
            -> tests/test_checkout.py

        tests.test_checkout.TestCheckout
            -> tests/test_checkout.py

    xunit2 reports may omit the `file` attribute, so classname is used
    as the fallback source for the path.
    """

    if (
        not isinstance(classname, str)
        or not classname.strip()
    ):
        raise PytestAdapterError(
            "JUnit testcase has neither a usable file nor classname"
        )

    parts = [
        part
        for part in classname.strip().split(".")
        if part
    ]

    if not parts:
        raise PytestAdapterError(
            "JUnit classname cannot be converted to a test path"
        )

    # Pytest class-based tests can produce classnames like:
    #
    # tests.test_checkout.TestCheckout
    #
    # The last component is the Python class rather than the module.
    if (
        len(parts) > 1
        and (
            parts[-1].startswith("Test")
            or parts[-1][:1].isupper()
        )
    ):
        parts = parts[:-1]

    path = "/".join(parts)

    if not path.endswith(".py"):
        path += ".py"

    return path


def normalize_pytest_test_id(
    test_file,
    test_name,
    classname=None,
):
    """
    Build TestBudget's stable pytest identity.

    TestBudget's shared pytest identity contract is:

        path::name

    Args:
        test_file:
            File path supplied by JUnit. May be None for xunit2.

        test_name:
            Pytest test name.

        classname:
            JUnit classname used when the file attribute is unavailable.

    Returns:
        A normalized TestBudget test ID.

    Raises:
        PytestAdapterError:
            If a stable identity cannot be produced.
    """

    if (
        not isinstance(test_name, str)
        or not test_name.strip()
    ):
        raise PytestAdapterError(
            "JUnit testcase has no test name"
        )

    test_name = test_name.strip()

    if (
        isinstance(test_file, str)
        and test_file.strip()
    ):
        path = _normalize_path(
            test_file
        )

    else:
        path = _file_from_classname(
            classname
        )

    if not path:
        raise PytestAdapterError(
            "JUnit testcase has no usable test path"
        )

    return f"{path}::{test_name}"


def _testcase_status(testcase):
    """
    Convert JUnit testcase children into TestBudget's status vocabulary.
    """

    if (
        testcase.find("failure") is not None
        or testcase.find("error") is not None
    ):
        return "failed"

    if testcase.find("skipped") is not None:
        return "skipped"

    return "passed"


def _testcase_duration(
    testcase,
    test_id,
):
    """
    Return testcase duration in seconds.

    JUnit allows producers to omit `time`, so missing time is represented
    as 0.0 rather than causing the complete report to fail.
    """

    raw_time = testcase.attrib.get(
        "time"
    )

    if raw_time in (
        None,
        "",
    ):
        return 0.0

    try:
        duration = float(
            raw_time
        )

    except (
        TypeError,
        ValueError,
    ) as error:
        raise PytestAdapterError(
            f"{test_id}: invalid JUnit time value: {raw_time}"
        ) from error

    if duration < 0:
        raise PytestAdapterError(
            f"{test_id}: JUnit duration cannot be negative"
        )

    return duration


def parse_pytest_junit(xml_path):
    """
    Parse pytest xunit1 or xunit2 JUnit XML.

    Both formats are accepted through the same parser. xunit1 commonly
    provides a `file` attribute, while xunit2 may require TestBudget to
    infer the file from `classname`.

    Repeated occurrences of the same test ID are recorded as attempts
    1, 2, 3, and so on.

    Args:
        xml_path:
            Path to a pytest-generated JUnit XML report.

    Returns:
        List of dictionaries containing:

        - test_id
        - status
        - duration_s
        - attempt

    Raises:
        PytestAdapterError:
            If the XML is missing, malformed, or cannot provide a stable
            test identity.
    """

    xml_path = Path(
        xml_path
    )

    if not xml_path.exists():
        raise PytestAdapterError(
            f"JUnit report does not exist: {xml_path}"
        )

    try:
        tree = ET.parse(
            xml_path
        )

    except ET.ParseError as error:
        raise PytestAdapterError(
            f"invalid JUnit XML: {xml_path}"
        ) from error

    root = tree.getroot()

    attempts = {}
    results = []

    for testcase in root.iter(
        "testcase"
    ):
        test_id = normalize_pytest_test_id(
            test_file=testcase.attrib.get(
                "file"
            ),
            test_name=testcase.attrib.get(
                "name"
            ),
            classname=testcase.attrib.get(
                "classname"
            ),
        )

        attempt = (
            attempts.get(
                test_id,
                0,
            )
            + 1
        )

        attempts[test_id] = attempt

        results.append(
            {
                "test_id": test_id,
                "status": _testcase_status(
                    testcase
                ),
                "duration_s": (
                    _testcase_duration(
                        testcase,
                        test_id,
                    )
                ),
                "attempt": attempt,
            }
        )

    return results

def load_selected_test_ids(
    plan_path,
):
    """
    Read pytest test IDs selected by a TestBudget plan.

    Args:
        plan_path:
            Path to `plan.json`.

    Returns:
        Selected pytest test IDs in plan order.

    Raises:
        PytestAdapterError:
            If the plan file does not exist or has an invalid structure.
    """

    plan_path = Path(
        plan_path
    )

    if not plan_path.exists():
        raise PytestAdapterError(
            f"TestBudget plan does not exist: {plan_path}"
        )

    try:
        plan = json.loads(
            plan_path.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as error:
        raise PytestAdapterError(
            f"invalid TestBudget plan JSON: {plan_path}"
        ) from error

    if not isinstance(plan, dict):
        raise PytestAdapterError(
            "TestBudget plan must be a JSON object"
        )

    selected = plan.get(
        "selected"
    )

    if not isinstance(selected, list):
        raise PytestAdapterError(
            "TestBudget plan must contain a selected list"
        )

    selected_ids = []
    seen = set()

    for index, entry in enumerate(
        selected,
        start=1,
    ):
        if not isinstance(entry, dict):
            raise PytestAdapterError(
                f"selected item {index} must be an object"
            )

        test_id = entry.get(
            "test_id"
        )

        if (
            not isinstance(test_id, str)
            or not test_id.strip()
        ):
            raise PytestAdapterError(
                f"selected item {index} has no valid test_id"
            )

        test_id = test_id.strip()

        # This adapter only owns pytest identities.
        # Playwright uses a different shared identity format.
        if "::" not in test_id:
            continue

        if test_id not in seen:
            selected_ids.append(
                test_id
            )

            seen.add(
                test_id
            )

    return selected_ids


def pytest_item_to_test_id(item):
    """
    Convert a collected pytest item into TestBudget's `path::name` identity.

    Pytest node IDs can contain class names:

        tests/test_cart.py::TestCart::test_add

    TestBudget's agreed identity is:

        tests/test_cart.py::test_add
    """

    nodeid = str(
        item.nodeid
    ).replace(
        "\\",
        "/",
    )

    parts = nodeid.split(
        "::"
    )

    if len(parts) < 2:
        raise PytestAdapterError(
            f"cannot normalize pytest nodeid: {nodeid}"
        )

    test_file = parts[0]
    test_name = parts[-1]

    return normalize_pytest_test_id(
        test_file,
        test_name,
    )


def pytest_addoption(parser):
    """
    Register TestBudget's pytest command-line options.
    """

    group = parser.getgroup(
        "testbudget"
    )

    group.addoption(
        "--testbudget-plan",
        action="store",
        default=None,
        metavar="PATH",
        help=(
            "Execute pytest tests selected by a TestBudget plan.json file."
        ),
    )


def pytest_collection_modifyitems(
    config,
    items,
):
    """
    Reorder and cut pytest collection using a TestBudget plan.

    When `--testbudget-plan` is not supplied, collection is left unchanged.

    When a plan is supplied:

    1. selected pytest IDs are read in plan order;
    2. collected items are mapped to TestBudget IDs;
    3. matching items are reordered to plan order;
    4. all remaining pytest items are reported as deselected.
    """

    plan_path = config.getoption(
        "--testbudget-plan"
    )

    if not plan_path:
        return

    try:
        selected_ids = (
            load_selected_test_ids(
                plan_path
            )
        )

    except PytestAdapterError as error:
        raise pytest.UsageError(
            str(error)
        ) from error

    collected_by_id = {}

    for item in items:
        try:
            test_id = (
                pytest_item_to_test_id(
                    item
                )
            )

        except PytestAdapterError as error:
            raise pytest.UsageError(
                str(error)
            ) from error

        collected_by_id.setdefault(
            test_id,
            [],
        ).append(
            item
        )

    selected_items = []

    for test_id in selected_ids:
        selected_items.extend(
            collected_by_id.get(
                test_id,
                [],
            )
        )

    selected_item_ids = {
        id(item)
        for item in selected_items
    }

    deselected_items = [
        item
        for item in items
        if id(item)
        not in selected_item_ids
    ]

    if deselected_items:
        config.hook.pytest_deselected(
            items=deselected_items
        )

    items[:] = selected_items