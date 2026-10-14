import xml.etree.ElementTree as ET


def parse_junit(xml_path):
    """
    Parse a JUnit XML report and return normalized test results.

    Each returned dictionary contains:
        test_name
        test_file
        status
        duration
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
        test_name = testcase.attrib.get("name", "unknown")
        test_file = testcase.attrib.get("classname", "")
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