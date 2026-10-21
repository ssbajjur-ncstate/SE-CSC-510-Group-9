from testbudget.feedback import nightly_failures

NIGHTLY = "n1"
PAY = "tests/test_pay.py::test_charge"
UI = "tests/test_ui.py::test_render"
CART = "tests/test_cart.py::test_add"


def make_result(sha, test_id, status, attempt=1):
    return {
        "sha": sha,
        "test_id": test_id,
        "status": status,
        "duration_s": 1.0,
        "attempt": attempt,
    }


def test_failed_nightly_tests_are_returned_sorted():
    results = [
        make_result(NIGHTLY, UI, "failed"),
        make_result(NIGHTLY, PAY, "failed"),
        make_result(NIGHTLY, CART, "passed"),
        make_result("other", CART, "failed"),
    ]
    assert nightly_failures(NIGHTLY, results) == [PAY, UI]


def test_test_that_passed_on_retry_is_not_a_failure():
    results = [
        make_result(NIGHTLY, PAY, "failed", attempt=1),
        make_result(NIGHTLY, PAY, "passed", attempt=2),
    ]
    assert nightly_failures(NIGHTLY, results) == []


def test_skipped_result_is_not_a_failure():
    assert nightly_failures(NIGHTLY, [make_result(NIGHTLY, PAY, "skipped")]) == []


def test_no_results_means_no_failures():
    assert nightly_failures(NIGHTLY, []) == []
