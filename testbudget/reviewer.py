from testbudget.db import load_history_records


class ReviewerCommandError(ValueError):
    """
    Raised when a TestBudget reviewer command is invalid or unauthorized.
    """


WRITE_PERMISSIONS = {
    "write",
    "maintain",
    "admin",
}


def has_write_permission(
    permission,
):
    """
    Return whether a resolved GitHub repository permission may override a plan.

    Args:
        permission:
            GitHub repository permission such as `read`, `triage`, `write`,
            `maintain`, or `admin`.

    Returns:
        True only for permissions allowed to trigger reviewer overrides.
    """

    if not isinstance(
        permission,
        str,
    ):
        return False

    return permission.strip().lower() in WRITE_PERMISSIONS


def known_test_ids_from_results(
    results,
):
    """
    Return stable test IDs observed in TestBudget history.

    Ordering follows first appearance in history. Duplicate IDs are removed.

    Args:
        results:
            Iterable of history result dictionaries.

    Raises:
        ReviewerCommandError:
            If a result does not contain a valid `test_id`.
    """

    known = []
    seen = set()

    for index, result in enumerate(
        results,
        start=1,
    ):
        if not isinstance(
            result,
            dict,
        ):
            raise ReviewerCommandError(f"history result {index} must be an object")

        test_id = result.get("test_id")

        if (
            not isinstance(
                test_id,
                str,
            )
            or not test_id.strip()
        ):
            raise ReviewerCommandError(f"history result {index} has no valid test_id")

        test_id = test_id.strip()

        if test_id not in seen:
            known.append(test_id)

            seen.add(test_id)

    return known


def load_known_test_ids(
    history_dir="history",
):
    """
    Load all known test IDs from TestBudget's canonical JSONL history.
    """

    _, results = load_history_records(history_dir)

    return known_test_ids_from_results(results)


def validate_test_ids(
    requested_test_ids,
    known_test_ids,
):
    """
    Validate reviewer-supplied test IDs against TestBudget history.

    Unknown IDs are rejected rather than silently accepted.

    Args:
        requested_test_ids:
            Test IDs requested by a reviewer-driven operation.

        known_test_ids:
            Test IDs observed in TestBudget history.

    Returns:
        A de-duplicated list preserving request order.

    Raises:
        ReviewerCommandError:
            If a requested test ID is malformed or unknown.
    """

    known = set(known_test_ids)

    validated = []
    seen = set()

    for index, test_id in enumerate(
        requested_test_ids,
        start=1,
    ):
        if (
            not isinstance(
                test_id,
                str,
            )
            or not test_id.strip()
        ):
            raise ReviewerCommandError(f"requested test ID {index} is invalid")

        test_id = test_id.strip()

        if test_id not in known:
            raise ReviewerCommandError(f"unknown test ID: {test_id}")

        if test_id not in seen:
            validated.append(test_id)

            seen.add(test_id)

    return validated


def parse_reviewer_command(
    comment_body,
    actor_permission,
):
    """
    Parse a TestBudget reviewer comment.

    Supported command:

        /testbudget full

    Unrelated comments return None so normal PR discussion does not cause an
    error.

    TestBudget-looking comments using unsupported syntax fail explicitly.

    Args:
        comment_body:
            GitHub issue/PR comment body.

        actor_permission:
            Permission already resolved by the GitHub integration layer.

    Returns:
        None for an unrelated comment.

        Otherwise:

        {
            "action": "full"
        }

    Raises:
        ReviewerCommandError:
            If the command is malformed, unsupported, or unauthorized.
    """

    if not isinstance(
        comment_body,
        str,
    ):
        return None

    lines = [line.strip() for line in comment_body.splitlines() if line.strip()]

    if not lines:
        return None

    command_line = lines[0]

    if not command_line.startswith("/testbudget"):
        return None

    parts = command_line.split()

    if parts != [
        "/testbudget",
        "full",
    ]:
        raise ReviewerCommandError(
            "unsupported TestBudget command; expected `/testbudget full`"
        )

    if not has_write_permission(actor_permission):
        raise ReviewerCommandError("reviewer does not have write permission")

    return {
        "action": "full",
    }
