import pytest
from hypothesis import given
from hypothesis import strategies as st

from testbudget.rules import (
    RuleContext,
    apply_rotation_limit,
    apply_rules,
    changed_tests_next,
    compute_skip_debt,
    file_of_test,
    full_suite_trigger,
    ordered_shas,
    pin_first,
    pinned_tests,
    recent_failures_next,
    recently_failed,
)


def make_test(name, score=1.0, duration=1.0):
    return {
        "test_name": name,
        "score": score,
        "duration": duration,
        "failure_count": 0,
        "linked_to_change": False,
        "reason": "historical runtime",
    }


def names(tests):
    return [test["test_name"] for test in tests]


RANKED = [
    make_test("tests/test_a.py::test_one", score=3.0),
    make_test("tests/test_b.py::test_two", score=2.0),
    make_test("tests/test_c.py::test_three", score=1.0),
]

test_ids = st.lists(
    st.text(alphabet="abcdefgh_", min_size=1, max_size=6).map(
        lambda name: f"tests/test_{name}.py::test_{name}"
    ),
    unique=True,
    min_size=1,
    max_size=12,
)


def test_pinned_test_moves_to_the_front():
    context = RuleContext(config={"pins": ["tests/test_c.py::test_three"]})
    result = pin_first(RANKED, context)
    assert names(result) == [
        "tests/test_c.py::test_three",
        "tests/test_a.py::test_one",
        "tests/test_b.py::test_two",
    ]
    assert result[0]["rule"] == "pinned"
    assert "rule" not in result[1]


def test_pins_as_mapping_of_test_to_files_are_read():
    config = {"pins": {"tests/test_b.py::test_two": ["src/pay.py"]}}
    assert pinned_tests(config) == {"tests/test_b.py::test_two"}


def test_several_pinned_tests_keep_their_ranked_order():
    pins = ["tests/test_c.py::test_three", "tests/test_b.py::test_two"]
    result = pin_first(RANKED, RuleContext(config={"pins": pins}))
    assert names(result)[:2] == pins[::-1]


def test_pin_for_an_unknown_test_is_ignored():
    context = RuleContext(config={"pins": ["tests/test_x.py::test_gone"]})
    assert names(pin_first(RANKED, context)) == names(RANKED)


def test_no_pins_leaves_the_order_unchanged():
    assert names(pin_first(RANKED, RuleContext())) == names(RANKED)


def test_pin_first_does_not_mutate_its_input():
    ranked = [dict(test) for test in RANKED]
    pin_first(ranked, RuleContext(config={"pins": ["tests/test_c.py::test_three"]}))
    assert ranked == RANKED


@pytest.mark.parametrize("pins", ["tests/test_a.py::test_one", 3, [""], [None]])
def test_malformed_pins_are_rejected(pins):
    with pytest.raises(ValueError, match="pin"):
        pin_first(RANKED, RuleContext(config={"pins": pins}))


@given(ids=test_ids, data=st.data())
def test_pinned_test_is_always_first(ids, data):
    pins = data.draw(st.lists(st.sampled_from(ids), min_size=1, unique=True))
    ranked = [make_test(test_id) for test_id in ids]
    result = pin_first(ranked, RuleContext(config={"pins": pins}))
    assert result[0]["test_name"] in pins
    assert set(names(result[: len(pins)])) == set(pins)


@pytest.mark.parametrize(
    ("test_id", "expected"),
    [
        ("tests/test_a.py::test_one", "tests/test_a.py"),
        ("tests/test_a.py::TestCase::test_one", "tests/test_a.py"),
        ("e2e/cart.spec.ts › adds an item", "e2e/cart.spec.ts"),
        (r"tests\test_a.py::test_one", "tests/test_a.py"),
        ("tests/test_a.py", "tests/test_a.py"),
    ],
)
def test_file_of_test_is_the_part_before_the_separator(test_id, expected):
    assert file_of_test(test_id) == expected


def test_test_whose_file_changed_moves_to_the_front():
    context = RuleContext(changed_files=["./tests/test_b.py", "src/pay.py"])
    result = changed_tests_next(RANKED, context)
    assert names(result)[0] == "tests/test_b.py::test_two"
    assert result[0]["rule"] == "changed test file"
    assert names(result)[1:] == [
        "tests/test_a.py::test_one",
        "tests/test_c.py::test_three",
    ]


def test_playwright_spec_change_moves_its_tests():
    ranked = [
        make_test("e2e/home.spec.ts › loads"),
        make_test("e2e/cart.spec.ts › adds"),
    ]
    context = RuleContext(changed_files=["e2e/cart.spec.ts"])
    assert names(changed_tests_next(ranked, context))[0] == "e2e/cart.spec.ts › adds"


def test_source_only_change_leaves_the_order_unchanged():
    context = RuleContext(changed_files=["src/pay.py"])
    assert names(changed_tests_next(RANKED, context)) == names(RANKED)


def test_changed_files_given_as_a_string_is_rejected():
    with pytest.raises(TypeError, match="list of paths"):
        changed_tests_next(RANKED, RuleContext(changed_files="tests/test_b.py"))


def make_run(sha, day, changed_files=()):
    return {
        "sha": sha,
        "timestamp": f"2026-10-{day:02d}T00:00:00Z",
        "branch": "main",
        "changed_files": list(changed_files),
    }


def make_result(sha, test_id, status="passed", attempt=1):
    return {
        "sha": sha,
        "test_id": test_id,
        "status": status,
        "duration_s": 1.0,
        "attempt": attempt,
    }


def test_runs_are_ordered_by_timestamp_not_file_order():
    runs = [make_run("c", 3), make_run("a", 1), make_run("b", 2), make_run("a", 1)]
    assert ordered_shas(runs) == ["a", "b", "c"]


def test_only_failures_inside_the_window_count():
    runs = [make_run(f"r{day}", day) for day in range(1, 5)]
    results = [
        make_result("r1", "tests/test_a.py::test_one", "failed"),
        make_result("r3", "tests/test_b.py::test_two", "failed"),
        make_result("r4", "tests/test_c.py::test_three", "passed"),
    ]
    assert recently_failed(runs, results, window=2) == {"tests/test_b.py::test_two"}
    assert recently_failed(runs, results, window=4) == {
        "tests/test_a.py::test_one",
        "tests/test_b.py::test_two",
    }
    assert recently_failed(runs, results, window=0) == set()


def test_failure_on_a_retried_attempt_still_counts():
    runs = [make_run("r1", 1)]
    results = [
        make_result("r1", "tests/test_c.py::test_three", "failed", attempt=1),
        make_result("r1", "tests/test_c.py::test_three", "passed", attempt=2),
    ]
    assert recently_failed(runs, results, window=1) == {"tests/test_c.py::test_three"}


def test_recently_failed_test_moves_to_the_front():
    runs = [make_run("r1", 1), make_run("r2", 2)]
    results = [make_result("r2", "tests/test_c.py::test_three", "failed")]
    context = RuleContext(
        runs=runs, results=results, config={"recent_failure_window": 1}
    )
    result = recent_failures_next(RANKED, context)
    assert names(result)[0] == "tests/test_c.py::test_three"
    assert result[0]["rule"] == "recent failure"


def test_empty_history_leaves_the_order_unchanged():
    assert names(recent_failures_next(RANKED, RuleContext())) == names(RANKED)


@pytest.mark.parametrize("window", [-1, 2.5, "3", True])
def test_bad_recent_failure_window_is_rejected(window):
    context = RuleContext(config={"recent_failure_window": window})
    with pytest.raises(ValueError, match="recent_failure_window"):
        recent_failures_next(RANKED, context)


def test_negative_window_is_rejected_directly():
    with pytest.raises(ValueError, match="non-negative"):
        recently_failed([], [], window=-1)


def test_skip_debt_counts_runs_since_the_test_last_ran():
    runs = [make_run(f"r{day}", day) for day in range(1, 6)]
    results = [
        make_result("r1", "tests/test_a.py::test_one"),
        make_result("r2", "tests/test_b.py::test_two", "skipped"),
        make_result("r5", "tests/test_c.py::test_three", "failed"),
        make_result("r1", "tests/test_c.py::test_three"),
    ]
    assert compute_skip_debt(runs, results) == {
        "tests/test_a.py::test_one": 4,
        "tests/test_b.py::test_two": 3,
        "tests/test_c.py::test_three": 0,
    }


def test_skip_debt_of_empty_history_is_empty():
    assert compute_skip_debt([], []) == {}


def test_result_for_an_unknown_sha_is_ignored():
    results = [make_result("ghost", "tests/test_a.py::test_one")]
    assert compute_skip_debt([make_run("r1", 1)], results) == {}


def test_test_at_the_rotation_limit_is_forced():
    runs = [make_run(f"r{day}", day) for day in range(1, 5)]
    results = [
        make_result("r1", "tests/test_a.py::test_one"),
        make_result("r4", "tests/test_b.py::test_two"),
    ]
    context = RuleContext(runs=runs, results=results, config={"rotation_limit": 3})
    result = {test["test_name"]: test for test in apply_rotation_limit(RANKED, context)}
    assert result["tests/test_a.py::test_one"]["skip_debt"] == 3
    assert result["tests/test_a.py::test_one"]["forced"] is True
    assert result["tests/test_b.py::test_two"]["forced"] is False
    assert result["tests/test_c.py::test_three"]["skip_debt"] == 0
    assert result["tests/test_c.py::test_three"]["forced"] is False


def test_rotation_limit_keeps_the_ranked_order():
    assert names(apply_rotation_limit(RANKED, RuleContext())) == names(RANKED)


@pytest.mark.parametrize("limit", [0, -2, 1.5, "10", None])
def test_bad_rotation_limit_is_rejected(limit):
    context = RuleContext(config={"rotation_limit": limit})
    with pytest.raises(ValueError, match="rotation_limit"):
        apply_rotation_limit(RANKED, context)


@given(
    ids=test_ids,
    limit=st.integers(min_value=1, max_value=8),
    extra=st.integers(min_value=0, max_value=4),
    data=st.data(),
)
def test_test_past_the_rotation_limit_is_always_forced(ids, limit, extra, data):
    target = data.draw(st.sampled_from(ids))
    others = [test_id for test_id in ids if test_id != target]
    runs = [make_run(f"r{day:02d}", day) for day in range(1, limit + extra + 2)]
    results = [make_result("r01", target)]
    for run in runs[1:]:
        ran = (
            data.draw(st.lists(st.sampled_from(others), unique=True)) if others else []
        )
        results += [make_result(run["sha"], test_id) for test_id in ran]
    ranked = [make_test(test_id) for test_id in ids]
    context = RuleContext(runs=runs, results=results, config={"rotation_limit": limit})
    forced = {
        t["test_name"] for t in apply_rotation_limit(ranked, context) if t["forced"]
    }
    assert target in forced


@pytest.mark.parametrize(
    ("changed", "reason"),
    [
        (["package-lock.json"], "lockfile changed: package-lock.json"),
        (["web/yarn.lock"], "lockfile changed: web/yarn.lock"),
        ([".github/workflows/x.yml"], "CI config changed: .github/workflows/x.yml"),
        ([".gitlab-ci.yml"], "CI config changed: .gitlab-ci.yml"),
        ([".env.local"], "environment file changed: .env.local"),
        (["app/.env"], "environment file changed: app/.env"),
        (
            [r".\.github\workflows\ci.yml"],
            "CI config changed: .github/workflows/ci.yml",
        ),
    ],
)
def test_risky_changed_file_triggers_the_full_suite(changed, reason):
    assert full_suite_trigger(RuleContext(changed_files=changed)) == reason


@pytest.mark.parametrize(
    ("ref", "reason"),
    [
        ("refs/tags/v1.0.0", "tag ref: refs/tags/v1.0.0"),
        ("refs/heads/release/2.1", "release ref: refs/heads/release/2.1"),
        ("release", "release ref: release"),
    ],
)
def test_tag_or_release_ref_triggers_the_full_suite(ref, reason):
    assert full_suite_trigger(RuleContext(ref=ref)) == reason


@pytest.mark.parametrize(
    "changed",
    [["src/pay.py"], ["docs/.envrc"], ["environment.py"], ["package.json"], []],
)
def test_ordinary_change_does_not_trigger_the_full_suite(changed):
    context = RuleContext(changed_files=changed, ref="refs/heads/feature/releases")
    assert full_suite_trigger(context) is None


def test_first_trigger_in_sorted_path_order_is_reported():
    context = RuleContext(changed_files=["yarn.lock", ".env", "src/a.py"])
    assert full_suite_trigger(context) == "environment file changed: .env"


@pytest.mark.parametrize("ref", ["", "   ", 7])
def test_bad_ref_is_rejected(ref):
    with pytest.raises(ValueError, match="ref"):
        full_suite_trigger(RuleContext(ref=ref))


def test_full_suite_trigger_rejects_changed_files_as_a_string():
    with pytest.raises(TypeError, match="list of paths"):
        full_suite_trigger(RuleContext(changed_files="package-lock.json"))


def full_context(**overrides):
    runs = [make_run(f"r{day}", day) for day in range(1, 4)]
    results = [
        make_result("r1", "tests/test_a.py::test_one"),
        make_result("r3", "tests/test_b.py::test_two", "failed"),
        make_result("r3", "tests/test_d.py::test_four"),
    ]
    fields = {
        "config": {"pins": ["tests/test_c.py::test_three"], "rotation_limit": 2},
        "changed_files": ["tests/test_d.py"],
        "runs": runs,
        "results": results,
    }
    fields.update(overrides)
    return RuleContext(**fields)


PIPELINE_RANKED = RANKED + [make_test("tests/test_d.py::test_four", score=0.5)]


def test_rules_apply_in_precedence_order():
    outcome = apply_rules(PIPELINE_RANKED, full_context())
    assert names(outcome["tests"]) == [
        "tests/test_c.py::test_three",
        "tests/test_d.py::test_four",
        "tests/test_b.py::test_two",
        "tests/test_a.py::test_one",
    ]
    assert [test.get("rule") for test in outcome["tests"]] == [
        "pinned",
        "changed test file",
        "recent failure",
        None,
    ]
    assert outcome["run_all"] is False
    assert outcome["trigger"] is None


def test_rotation_limit_marks_tests_inside_the_pipeline():
    tests = {
        t["test_name"]: t for t in apply_rules(PIPELINE_RANKED, full_context())["tests"]
    }
    assert tests["tests/test_a.py::test_one"]["forced"] is True
    assert tests["tests/test_a.py::test_one"]["skip_debt"] == 2
    assert tests["tests/test_b.py::test_two"]["forced"] is False


def test_test_matching_several_rules_takes_the_highest_tag():
    context = full_context(changed_files=["tests/test_c.py"])
    first = apply_rules(PIPELINE_RANKED, context)["tests"][0]
    assert first["test_name"] == "tests/test_c.py::test_three"
    assert first["rule"] == "pinned"


def test_full_suite_trigger_forces_every_test():
    context = full_context(changed_files=["poetry.lock"])
    outcome = apply_rules(PIPELINE_RANKED, context)
    assert outcome["run_all"] is True
    assert outcome["trigger"] == "lockfile changed: poetry.lock"
    assert all(test["forced"] for test in outcome["tests"])


def test_apply_rules_on_empty_inputs_returns_nothing_to_run():
    outcome = apply_rules([], RuleContext())
    assert outcome == {"tests": [], "run_all": False, "trigger": None}


def test_apply_rules_does_not_mutate_its_input():
    ranked = [dict(test) for test in PIPELINE_RANKED]
    apply_rules(ranked, full_context())
    assert ranked == PIPELINE_RANKED


def test_apply_rules_rejects_a_malformed_config():
    with pytest.raises(ValueError, match="rotation_limit"):
        apply_rules(PIPELINE_RANKED, full_context(config={"rotation_limit": "x"}))


@given(ids=test_ids, data=st.data())
def test_pinned_test_is_always_first_after_every_rule(ids, data):
    pins = data.draw(st.lists(st.sampled_from(ids), min_size=1, unique=True))
    changed = data.draw(st.lists(st.sampled_from(ids), unique=True))
    failed = data.draw(st.lists(st.sampled_from(ids), unique=True))
    runs = [make_run("r1", 1)]
    results = [make_result("r1", test_id, "failed") for test_id in failed]
    context = RuleContext(
        config={"pins": pins},
        changed_files=[test_id.split("::")[0] for test_id in changed],
        runs=runs,
        results=results,
    )
    ranked = [make_test(test_id) for test_id in ids]
    outcome = apply_rules(ranked, context)
    assert outcome["tests"][0]["test_name"] in pins
    assert outcome["tests"][0]["rule"] == "pinned"


@given(ids=test_ids, data=st.data())
def test_identical_inputs_give_identical_rule_output(ids, data):
    pins = data.draw(st.lists(st.sampled_from(ids), unique=True))
    ranked = [make_test(test_id) for test_id in ids]
    context = RuleContext(config={"pins": pins})
    assert apply_rules(ranked, context) == apply_rules(ranked, context)
