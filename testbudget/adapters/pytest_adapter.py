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