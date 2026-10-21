class AuditModeError(ValueError):
    """
    Raised when a TestBudget execution policy cannot be constructed safely.
    """


def _unique_test_ids(
    test_ids,
):
    """
    Validate and de-duplicate test IDs while preserving order.
    """

    unique = []
    seen = set()

    for index, test_id in enumerate(
        test_ids,
        start=1,
    ):
        if (
            not isinstance(
                test_id,
                str,
            )
            or not test_id.strip()
        ):
            raise AuditModeError(f"test ID {index} is invalid")

        test_id = test_id.strip()

        if test_id not in seen:
            unique.append(test_id)

            seen.add(test_id)

    return unique


def _plan_test_ids(
    plan,
    field,
):
    """
    Extract test IDs from one TestBudget plan list.
    """

    entries = plan.get(field)

    if not isinstance(
        entries,
        list,
    ):
        raise AuditModeError(f"plan must contain a {field} list")

    test_ids = []

    for index, entry in enumerate(
        entries,
        start=1,
    ):
        if not isinstance(
            entry,
            dict,
        ):
            raise AuditModeError(f"{field} item {index} must be an object")

        test_id = entry.get("test_id")

        if (
            not isinstance(
                test_id,
                str,
            )
            or not test_id.strip()
        ):
            raise AuditModeError(f"{field} item {index} has no valid test_id")

        test_ids.append(test_id.strip())

    return test_ids


def build_execution_policy(
    plan,
    all_test_ids,
    *,
    audit_mode=False,
    force_full=False,
):
    """
    Decide which tests should actually execute.

    Normal mode executes only tests selected by TestBudget.

    Audit mode executes the complete known suite but leaves the original
    TestBudget plan untouched so reporting can show what TestBudget would
    have selected and skipped.

    A reviewer full-suite override also executes the complete known suite.

    Args:
        plan:
            TestBudget plan dictionary.

        all_test_ids:
            Complete set of tests known for this execution environment.

        audit_mode:
            Whether audit mode is enabled.

        force_full:
            Whether an authorized reviewer requested `/testbudget full`.

    Returns:
        A new execution-policy dictionary.

    Raises:
        AuditModeError:
            If the plan is malformed or references a test unknown to the
            supplied complete test set.
    """

    if not isinstance(
        plan,
        dict,
    ):
        raise AuditModeError("plan must be an object")

    all_tests = _unique_test_ids(all_test_ids)

    known = set(all_tests)

    planned_selected = _plan_test_ids(
        plan,
        "selected",
    )

    planned_skipped = _plan_test_ids(
        plan,
        "skipped",
    )

    referenced = planned_selected + planned_skipped

    unknown = [test_id for test_id in referenced if test_id not in known]

    if unknown:
        raise AuditModeError("plan references unknown test ID: " + unknown[0])

    if force_full:
        mode = "reviewer_full"
        execute_test_ids = list(all_tests)

    elif audit_mode:
        mode = "audit"
        execute_test_ids = list(all_tests)

    else:
        mode = "normal"
        execute_test_ids = list(planned_selected)

    return {
        "mode": mode,
        "audit_mode": bool(audit_mode),
        "force_full": bool(force_full),
        "execute_test_ids": (execute_test_ids),
        "planned_selected_test_ids": list(planned_selected),
        "planned_skipped_test_ids": list(planned_skipped),
    }


def apply_reviewer_command(
    plan,
    all_test_ids,
    command,
    *,
    audit_mode=False,
):
    """
    Build execution policy after applying a parsed reviewer command.

    `None` means no reviewer override.

    The only currently supported command is:

        {"action": "full"}
    """

    if command is None:
        return build_execution_policy(
            plan,
            all_test_ids,
            audit_mode=audit_mode,
            force_full=False,
        )

    if (
        not isinstance(
            command,
            dict,
        )
        or command.get("action") != "full"
    ):
        raise AuditModeError("unsupported reviewer command")

    return build_execution_policy(
        plan,
        all_test_ids,
        audit_mode=audit_mode,
        force_full=True,
    )
