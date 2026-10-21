import xml.etree.ElementTree as ET

from testbudget.adapters.pytest_adapter import normalize_pytest_test_id


def parse_junit(xml_path):
    """
    Parse a JUnit XML report and return normalized test results.

    Test identities follow the shared pytest contract ``path::name``, the
    same format ``links --build`` writes. The path comes from the testcase
    ``file`` attribute when present, otherwise from the dotted classname
    (``tests.test_ranker`` -> ``tests/test_ranker.py``).

    Args:
        xml_path: Path to a pytest JUnit XML report.

    Returns:
        List of dictionaries containing:
            test_name: the ``path::name`` test ID
            test_file: the normalized test file path
            status
            duration

    Raises:
        PytestAdapterError: If a testcase has no name, or neither a file
            nor a classname to build its path from.
    """

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # JUnit files may contain either:
    #
    # <testsuite>
    #     <testcase />
    # </testsuite>
    #
    # or:
    #
    # <testsuites>
    #     <testsuite>
    #         <testcase />
    #     </testsuite>
    # </testsuites>

    if root.tag == "testsuite":
        testcases = root.findall("testcase")
    else:
        testcases = root.findall(".//testcase")

    results = []

    for testcase in testcases:
        test_name = normalize_pytest_test_id(
            test_file=testcase.attrib.get("file"),
            test_name=testcase.attrib.get("name"),
            classname=testcase.attrib.get("classname"),
        )
        test_file = test_name.split("::", 1)[0]
        duration = float(testcase.attrib.get("time", 0.0))

        failure = testcase.find("failure")
        error = testcase.find("error")
        skipped = testcase.find("skipped")

        if failure is not None or error is not None:
            status = "failed"
        elif skipped is not None:
            status = "skipped"
        else:
            status = "passed"

        result = {
            "test_name": test_name,
            "test_file": test_file,
            "status": status,
            "duration": duration,
        }

        results.append(result)

    return results
