import pytest

from testbudget.riskmap import (
    change_risk,
    file_failure_weights,
    global_failure_prior,
)


def make_run(sha, changed_files):
    return {
        "sha": sha,
        "timestamp": "2026-10-01T00:00:00Z",
        "branch": "main",
        "changed_files": changed_files,
    }


def make_result(sha, status, test_id="tests/test_app.py::test_ok"):
    return {
        "sha": sha,
        "test_id": test_id,
        "status": status,
        "duration_s": 1.0,
        "attempt": 1,
    }


@pytest.fixture
def history():
    runs = [
        make_run("a1", ["src/pay.py", "src/ui.py"]),
        make_run("a2", ["src/pay.py"]),
        make_run("a3", ["src/ui.py"]),
        make_run("a4", ["src/docs.py"]),
    ]
    results = [
        make_result("a1", "failed"),
        make_result("a2", "passed"),
        make_result("a2", "failed", "tests/test_pay.py::test_charge"),
        make_result("a3", "passed"),
        make_result("a4", "passed"),
        make_result("a4", "skipped"),
    ]
    return runs, results


def test_file_that_always_precedes_failures_gets_highest_weight(history):
    weights = file_failure_weights(*history)
    assert max(weights, key=weights.get) == "src/pay.py"
    assert weights["src/pay.py"] == pytest.approx(3 / 4)


def test_weights_are_laplace_smoothed(history):
    weights = file_failure_weights(*history)
    assert weights["src/ui.py"] == pytest.approx(2 / 4)
    assert weights["src/docs.py"] == pytest.approx(1 / 3)


def test_skipped_results_do_not_count_as_failures(history):
    weights = file_failure_weights(*history)
    assert weights["src/docs.py"] < weights["src/ui.py"]


def test_duplicate_run_records_count_once():
    runs = [make_run("a1", ["src/pay.py"]), make_run("a1", ["src/pay.py"])]
    weights = file_failure_weights(runs, [make_result("a1", "failed")])
    assert weights["src/pay.py"] == pytest.approx(2 / 3)


def test_weights_are_sorted_by_path(history):
    weights = file_failure_weights(*history)
    assert list(weights) == sorted(weights)


def test_empty_history_has_no_file_weights():
    assert file_failure_weights([], []) == {}


def test_run_without_changed_files_adds_no_weights():
    runs = [{"sha": "a1", "changed_files": []}, {"sha": "a2"}]
    assert file_failure_weights(runs, [make_result("a1", "failed")]) == {}


def test_run_missing_sha_raises_key_error():
    with pytest.raises(KeyError):
        file_failure_weights([{"changed_files": ["src/pay.py"]}], [])


def test_global_prior_is_smoothed_failing_run_share(history):
    assert global_failure_prior(*history) == pytest.approx((2 + 1) / (4 + 2))


def test_global_prior_of_empty_history_is_one_half():
    assert global_failure_prior([], []) == 0.5


def test_global_prior_ignores_results_without_a_run():
    runs = [make_run("a1", ["src/pay.py"])]
    assert global_failure_prior(runs, [make_result("zz", "failed")]) == 1 / 3


def test_change_risk_sums_known_file_weights():
    weights = {"src/pay.py": 0.75, "src/ui.py": 0.5}
    assert change_risk(["src/pay.py", "src/ui.py"], weights, 0.2) == 1.25


def test_unknown_file_gets_the_prior():
    weights = {"src/pay.py": 0.75}
    assert change_risk(["src/new.py"], weights, 0.2) == 0.2
    assert change_risk(["src/pay.py", "src/new.py"], weights, 0.2) == 0.95


def test_empty_history_returns_the_prior_for_every_file():
    runs, results = [], []
    weights = file_failure_weights(runs, results)
    prior = global_failure_prior(runs, results)
    changed = ["src/a.py", "src/b.py", "src/c.py"]
    assert change_risk(changed, weights, prior) == pytest.approx(3 * prior)


def test_duplicate_changed_files_count_once():
    assert change_risk(["src/a.py", "src/a.py"], {"src/a.py": 0.4}, 0.2) == 0.4


def test_change_risk_does_not_depend_on_file_order():
    weights = {"a": 0.1, "b": 0.2, "c": 0.3}
    assert change_risk(["c", "a", "b"], weights, 0.5) == change_risk(
        ["a", "b", "c"], weights, 0.5
    )


def test_empty_change_set_has_zero_risk():
    assert change_risk([], {"src/pay.py": 0.75}, 0.2) == 0.0


@pytest.mark.parametrize("prior", [-0.1, 1.5])
def test_change_risk_rejects_prior_outside_unit_interval(prior):
    with pytest.raises(ValueError, match="prior"):
        change_risk(["src/a.py"], {}, prior)
