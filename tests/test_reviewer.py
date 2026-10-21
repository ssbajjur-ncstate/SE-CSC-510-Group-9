import json

import pytest

from testbudget.reviewer import (
    ReviewerCommandError,
    has_write_permission,
    known_test_ids_from_results,
    load_known_test_ids,
    parse_reviewer_command,
    validate_test_ids,
)


def test_write_permission_is_allowed():
    assert has_write_permission("write") is True


def test_maintain_permission_is_allowed():
    assert has_write_permission("maintain") is True


def test_admin_permission_is_allowed():
    assert has_write_permission("admin") is True


def test_read_permission_is_rejected():
    assert has_write_permission("read") is False


def test_triage_permission_is_rejected():
    assert has_write_permission("triage") is False


def test_full_command_parses_for_writer():
    command = parse_reviewer_command(
        "/testbudget full",
        "write",
    )

    assert command == {
        "action": "full",
    }


def test_command_allows_surrounding_whitespace():
    command = parse_reviewer_command(
        "   /testbudget full   ",
        "admin",
    )

    assert command == {
        "action": "full",
    }


def test_unrelated_comment_is_ignored():
    command = parse_reviewer_command(
        "Looks good to me.",
        "write",
    )

    assert command is None


def test_read_user_cannot_request_full():
    with pytest.raises(
        ReviewerCommandError,
        match="write permission",
    ):
        parse_reviewer_command(
            "/testbudget full",
            "read",
        )


def test_triage_user_cannot_request_full():
    with pytest.raises(
        ReviewerCommandError,
        match="write permission",
    ):
        parse_reviewer_command(
            "/testbudget full",
            "triage",
        )


def test_unknown_command_is_rejected():
    with pytest.raises(
        ReviewerCommandError,
        match="unsupported",
    ):
        parse_reviewer_command(
            "/testbudget destroy",
            "admin",
        )


def test_extra_command_arguments_are_rejected():
    with pytest.raises(
        ReviewerCommandError,
        match="unsupported",
    ):
        parse_reviewer_command(
            "/testbudget full now",
            "admin",
        )


def test_known_test_ids_preserve_first_seen_order():
    results = [
        {"test_id": ("tests/test_cart.py::test_cart")},
        {"test_id": ("tests/test_login.py::test_login")},
        {"test_id": ("tests/test_cart.py::test_cart")},
    ]

    assert known_test_ids_from_results(results) == [
        ("tests/test_cart.py::test_cart"),
        ("tests/test_login.py::test_login"),
    ]


def test_known_requested_test_id_is_accepted():
    known = [("tests/test_cart.py::test_cart")]

    requested = [("tests/test_cart.py::test_cart")]

    assert (
        validate_test_ids(
            requested,
            known,
        )
        == requested
    )


def test_unknown_requested_test_id_is_rejected():
    known = [("tests/test_cart.py::test_cart")]

    with pytest.raises(
        ReviewerCommandError,
        match="unknown test ID",
    ):
        validate_test_ids(
            [("tests/test_unknown.py::test_unknown")],
            known,
        )


def test_load_known_test_ids_from_history(
    tmp_path,
):
    history = tmp_path / "history"

    history.mkdir()

    run = {
        "sha": "abc123",
        "timestamp": ("2026-10-21T10:00:00Z"),
        "branch": "main",
        "changed_files": [],
    }

    result = {
        "sha": "abc123",
        "test_id": ("tests/test_cart.py::test_cart"),
        "status": "passed",
        "duration_s": 1.0,
        "attempt": 1,
    }

    (history / "runs.jsonl").write_text(
        json.dumps(run) + "\n",
        encoding="utf-8",
    )

    (history / "results.jsonl").write_text(
        json.dumps(result) + "\n",
        encoding="utf-8",
    )

    assert load_known_test_ids(history) == [("tests/test_cart.py::test_cart")]
