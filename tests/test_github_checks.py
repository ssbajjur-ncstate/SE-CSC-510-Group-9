import json
from pathlib import Path

import pytest

from testbudget.github.checks import (
    build_annotations,
    build_payloads,
    build_summary,
    build_text,
    get_token,
    page_annotations,
    publish_check_run,
    test_file as file_of,
)

PLAN = json.loads((Path(__file__).parent.parent / "fixtures" / "plan.json").read_text())


def plan_with_skipped(n):
    plan = dict(PLAN)
    plan["skipped"] = [
        {"test_id": f"tests/test_{i}.py::test_x", "skip_reason": "over budget", "skip_debt": 1}
        for i in range(n)
    ]
    return plan


class FakeRequest:
    def __init__(self, existing=None):
        self.calls = []
        self.existing = existing or []

    def __call__(self, method, url, token, body=None):
        self.calls.append((method, url, body))
        if method == "GET":
            return {"check_runs": self.existing}
        return {"id": 99}


def test_summary_mentions_budget_risk_and_catch_rate():
    text = build_summary(PLAN)
    assert "medium" in text and "120s" in text and "87%" in text


def test_summary_handles_unknown_catch_rate():
    plan = dict(PLAN, catch_rate_estimate=None)
    assert "unknown" in build_summary(plan)


def test_text_lists_reasons_and_skip_debt():
    text = build_text(PLAN)
    assert "changed file" in text and "skip debt 2" in text


def test_text_with_nothing_selected_says_none():
    assert "- none" in build_text(dict(PLAN, selected=[]))


def test_test_file_handles_pytest_and_playwright_ids():
    assert file_of("tests/a.py::test_x") == "tests/a.py"
    assert file_of("e2e/home.spec.ts › loads") == "e2e/home.spec.ts"
    assert file_of("plain") == "plain"


def test_annotation_levels_follow_skip_debt():
    levels = {a["path"]: a["annotation_level"] for a in build_annotations(PLAN)}
    assert levels["tests/test_profile.py"] == "warning"
    assert levels["e2e/home.spec.ts"] == "notice"


def test_paging_at_exactly_50_is_one_page():
    assert [len(p) for p in page_annotations(build_annotations(plan_with_skipped(50)))] == [50]


def test_paging_at_51_is_two_pages():
    assert [len(p) for p in page_annotations(build_annotations(plan_with_skipped(51)))] == [50, 1]


def test_paging_120_gives_50_50_20():
    assert [len(p) for p in page_annotations(build_annotations(plan_with_skipped(120)))] == [50, 50, 20]


def test_paging_empty_gives_one_empty_page():
    assert page_annotations([]) == [[]]


def test_paging_rejects_bad_page_size():
    with pytest.raises(ValueError):
        page_annotations([], size=0)


def test_missing_plan_key_raises():
    broken = {k: v for k, v in PLAN.items() if k != "skipped"}
    with pytest.raises(ValueError):
        build_payloads(broken)


def test_first_payload_creates_and_later_payloads_only_update():
    payloads = build_payloads(plan_with_skipped(51))
    assert len(payloads) == 2
    assert payloads[0]["head_sha"] == "abc1234" and payloads[0]["name"] == "TestBudget"
    assert "head_sha" not in payloads[1]


def test_missing_token_raises():
    with pytest.raises(RuntimeError):
        get_token({})


def test_token_is_read_from_environment():
    assert get_token({"GITHUB_TOKEN": "t"}) == "t"


def test_publish_creates_when_no_existing_check():
    fake = FakeRequest()
    assert publish_check_run(PLAN, "o/r", "tok", request=fake) == 99
    assert [c[0] for c in fake.calls] == ["GET", "POST"]


def test_publish_updates_existing_check_in_place():
    fake = FakeRequest(existing=[{"id": 7}])
    assert publish_check_run(PLAN, "o/r", "tok", request=fake) == 7
    assert [c[0] for c in fake.calls] == ["GET", "PATCH"]
    assert "head_sha" not in fake.calls[1][2]


def test_publish_sends_one_extra_patch_for_51_annotations():
    fake = FakeRequest()
    publish_check_run(plan_with_skipped(51), "o/r", "tok", request=fake)
    assert [c[0] for c in fake.calls] == ["GET", "POST", "PATCH"]
