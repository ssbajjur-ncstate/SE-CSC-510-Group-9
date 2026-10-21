import pytest

from testbudget.feedback import attribute_misses, link_strength, nightly_failures

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


def make_run(sha, changed_files=(), timestamp="2026-10-20T02:00:00Z"):
    return {
        "sha": sha,
        "timestamp": timestamp,
        "branch": "main",
        "changed_files": list(changed_files),
    }


def make_plan(sha, selected=(), skipped=()):
    return {
        "sha": sha,
        "risk_level": "low",
        "budget_s": 60.0,
        "selected": [
            {"test_id": test_id, "reason": "changed file", "duration_s": 1.0}
            for test_id in selected
        ],
        "skipped": [
            {"test_id": test_id, "skip_reason": "budget exhausted", "skip_debt": 1}
            for test_id in skipped
        ],
        "catch_rate_estimate": 0.9,
    }


RUNS = [
    make_run(NIGHTLY, timestamp="2026-10-21T02:00:00Z"),
    make_run("p71", ["src/pay.py"]),
    make_run("p72", ["src/ui.py"]),
    make_run("p73", ["src/pay.py", "src/money.py"]),
]


def test_seeded_miss_returns_the_pr_that_skipped_the_test():
    results = [make_result(NIGHTLY, PAY, "failed"), make_result(NIGHTLY, UI, "passed")]
    plans = {
        "71": make_plan("p71", skipped=[PAY]),
        "72": make_plan("p72", selected=[PAY], skipped=[UI]),
    }
    attribution = attribute_misses(NIGHTLY, RUNS, results, plans, LINKS)
    assert attribution["failed_tests"] == [PAY]
    assert attribution["suspects"] == [
        {"pr": "71", "sha": "p71", "missed_tests": [PAY], "link_strength": 1.0}
    ]
    assert attribution["misses"] == [
        {
            "nightly_sha": NIGHTLY,
            "timestamp": "2026-10-21T02:00:00Z",
            "test_id": PAY,
            "prs": ["71"],
        }
    ]


def test_no_miss_returns_no_suspects():
    results = [make_result(NIGHTLY, PAY, "failed")]
    plans = {"71": make_plan("p71", selected=[PAY]), "72": make_plan("p72")}
    attribution = attribute_misses(NIGHTLY, RUNS, results, plans, LINKS)
    assert attribution["failed_tests"] == [PAY]
    assert attribution["suspects"] == []
    assert attribution["misses"] == []


def test_green_nightly_returns_nothing():
    results = [make_result(NIGHTLY, PAY, "passed")]
    plans = {"71": make_plan("p71", skipped=[PAY])}
    attribution = attribute_misses(NIGHTLY, RUNS, results, plans, LINKS)
    assert attribution["failed_tests"] == []
    assert attribution["suspects"] == []


def test_flaky_nightly_failure_is_not_attributed():
    results = [
        make_result(NIGHTLY, PAY, "failed", attempt=1),
        make_result(NIGHTLY, PAY, "passed", attempt=2),
    ]
    plans = {"71": make_plan("p71", skipped=[PAY])}
    assert attribute_misses(NIGHTLY, RUNS, results, plans, LINKS)["suspects"] == []


def test_several_prs_are_ranked_by_link_strength():
    results = [make_result(NIGHTLY, PAY, "failed"), make_result(NIGHTLY, UI, "failed")]
    plans = {
        "70": make_plan("p_unknown", skipped=[PAY]),
        "71": make_plan("p71", skipped=[PAY]),
        "72": make_plan("p72", skipped=[PAY, UI]),
        "73": make_plan("p73", skipped=[PAY]),
    }
    attribution = attribute_misses(NIGHTLY, RUNS, results, plans, LINKS)
    ranked = [(s["pr"], s["link_strength"]) for s in attribution["suspects"]]
    # 73 changed pay.py and money.py (1.5); 71 changed pay.py (1.0);
    # 72 changed ui.py, linked to UI only (1.0), tie broken by PR id;
    # 70's plan sha has no run in history, so it has no changed files.
    assert ranked == [("73", 1.5), ("71", 1.0), ("72", 1.0), ("70", 0.0)]
    assert [(m["test_id"], m["prs"]) for m in attribution["misses"]] == [
        (PAY, ["73", "71", "70", "72"]),
        (UI, ["72"]),
    ]


def test_attribution_is_deterministic_and_does_not_mutate_inputs():
    results = [make_result(NIGHTLY, PAY, "failed")]
    plans = {
        "72": make_plan("p72", skipped=[PAY]),
        "71": make_plan("p71", skipped=[PAY]),
    }
    before = repr((RUNS, results, plans, LINKS))
    first = attribute_misses(NIGHTLY, RUNS, results, plans, LINKS)
    reordered = dict(reversed(list(plans.items())))
    assert (
        attribute_misses(NIGHTLY, list(reversed(RUNS)), results, reordered, LINKS)
        == first
    )
    assert repr((RUNS, results, plans, LINKS)) == before


def test_empty_plans_and_links_return_nothing():
    results = [make_result(NIGHTLY, PAY, "failed")]
    attribution = attribute_misses(NIGHTLY, RUNS, results, {}, {})
    assert attribution == {
        "nightly_sha": NIGHTLY,
        "failed_tests": [PAY],
        "suspects": [],
        "misses": [],
    }


def test_empty_history_fails_with_a_clear_message():
    with pytest.raises(ValueError, match="not in the run history"):
        attribute_misses(NIGHTLY, [], [], {}, {})


@pytest.mark.parametrize(
    ("plan", "message"),
    [
        ([], "must be an object"),
        ({"skipped": []}, "has no sha"),
        ({"sha": "p71"}, "has no skipped list"),
        ({"sha": "p71", "skipped": [PAY]}, "has a skipped entry without test_id"),
    ],
)
def test_malformed_plan_is_rejected(plan, message):
    results = [make_result(NIGHTLY, PAY, "failed")]
    with pytest.raises(ValueError, match=f"PR 71 {message}"):
        attribute_misses(NIGHTLY, RUNS, results, {"71": plan}, LINKS)
