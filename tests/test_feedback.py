import pytest

from testbudget.feedback import link_strength, nightly_failures

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


LINKS = {
    PAY: [
        {"file": "src/pay.py", "source": "import", "weight": 1.0},
        {"file": "src/money.py", "source": "cofail", "weight": 0.5},
    ],
    UI: [{"file": "src/ui.py", "source": "import", "weight": 1.0}],
}


def test_link_strength_sums_links_to_changed_files():
    changed = ["src/pay.py", "src/money.py", "src/pay.py", "README.md"]
    assert link_strength(PAY, changed, LINKS) == 1.5


def test_test_without_links_to_the_change_has_zero_strength():
    assert link_strength(PAY, ["src/ui.py"], LINKS) == 0.0
    assert link_strength(CART, ["src/pay.py"], LINKS) == 0.0


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        ("src/pay.py", "must be a list"),
        (["src/pay.py"], "object with a file"),
        ([{"source": "import", "weight": 1.0}], "object with a file"),
        ([{"file": "src/pay.py", "weight": -1}], "non-negative number"),
        ([{"file": "src/pay.py", "weight": "high"}], "non-negative number"),
        ([{"file": "src/pay.py"}], "non-negative number"),
    ],
)
def test_malformed_links_are_rejected(entries, message):
    with pytest.raises(ValueError, match=message):
        link_strength(PAY, ["src/pay.py"], {PAY: entries})
