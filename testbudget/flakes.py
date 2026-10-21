from collections import defaultdict


class FlakeFilterError(ValueError):
    """
    Raised when history results cannot be classified safely.
    """


REQUIRED_RESULT_FIELDS = {
    "sha",
    "test_id",
    "status",
    "duration_s",
    "attempt",
}

ALLOWED_STATUSES = {
    "passed",
    "failed",
    "skipped",
}


def _validate_result(
    result,
    index,
):
    """
    Validate one TestBudget history result.

    The flake filter consumes the shared `results.jsonl` contract but does
    not modify or persist the source history.
    """

    if not isinstance(result, dict):
        raise FlakeFilterError(f"result {index} must be an object")

    missing = sorted(REQUIRED_RESULT_FIELDS - result.keys())

    if missing:
        raise FlakeFilterError(
            f"result {index} is missing required fields: " + ", ".join(missing)
        )

    sha = result["sha"]
    test_id = result["test_id"]
    status = result["status"]
    duration_s = result["duration_s"]
    attempt = result["attempt"]

    if not isinstance(sha, str) or not sha.strip():
        raise FlakeFilterError(f"result {index} has an invalid sha")

    if not isinstance(test_id, str) or not test_id.strip():
        raise FlakeFilterError(f"result {index} has an invalid test_id")

    if status not in ALLOWED_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_STATUSES))

        raise FlakeFilterError(
            f"result {index} has unsupported status "
            f"{status!r}; expected one of: {allowed}"
        )

    if (
        isinstance(duration_s, bool)
        or not isinstance(
            duration_s,
            (int, float),
        )
        or duration_s < 0
    ):
        raise FlakeFilterError(f"result {index} has an invalid duration_s")

    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise FlakeFilterError(f"result {index} has an invalid attempt")


def mark_flaky_failures(
    results,
):
    """
    Annotate historical TestBudget results with flake information.

    A failed result is marked flaky when the same `test_id` also passes on
    the same Git SHA.

    Two cases are distinguished:

    `passed_on_retry`
        A passing record exists on the same SHA with a larger attempt number.

    `passed_on_same_sha`
        The test both failed and passed on the same SHA, but the pass is not
        represented as a later numbered retry. This covers separate repeated
        executions of identical code.

    Args:
        results:
            Iterable of result dictionaries following TestBudget's shared
            history result contract.

    Returns:
        A new list of dictionaries in the original input order.

        Every returned dictionary contains two derived fields:

        - `flaky`: boolean
        - `flake_reason`: string or None

    The input dictionaries are never modified.
    """

    annotated = []

    grouped = defaultdict(list)

    for index, result in enumerate(
        results,
        start=1,
    ):
        _validate_result(
            result,
            index,
        )

        copied = dict(result)

        copied["flaky"] = False
        copied["flake_reason"] = None

        annotated.append(copied)

        key = (
            copied["sha"],
            copied["test_id"],
        )

        grouped[key].append(copied)

    for group_results in grouped.values():
        passes = [result for result in group_results if result["status"] == "passed"]

        if not passes:
            continue

        failures = [result for result in group_results if result["status"] == "failed"]

        for failure in failures:
            later_retry_pass = any(
                passed["attempt"] > failure["attempt"] for passed in passes
            )

            failure["flaky"] = True

            if later_retry_pass:
                failure["flake_reason"] = "passed_on_retry"

            else:
                failure["flake_reason"] = "passed_on_same_sha"

    return annotated


def filter_non_flaky_failures(
    results,
):
    """
    Return only failures that remain after flake filtering.

    This helper is intended for evaluation and replay code that needs to
    count real historical failures without treating flaky failures as misses.
    """

    annotated = mark_flaky_failures(results)

    return [
        result
        for result in annotated
        if (result["status"] == "failed" and not result["flaky"])
    ]
