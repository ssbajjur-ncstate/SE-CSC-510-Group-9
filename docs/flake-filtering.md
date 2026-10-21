# Flake filtering

TestBudget uses historical failures to estimate risk and evaluate whether a
budgeted plan would have caught past failures.

Flaky failures can distort both calculations.

The flake filter therefore derives whether historical failures should count
as real failures.

## What is a flaky failure?

TestBudget marks a failed result as flaky when the same test passes on the
same Git SHA.

The same SHA matters because it means the code under test did not change.

## Pass on retry

Example:

```text
SHA: abc123
Test: tests/test_cart.py::test_cart

attempt 1: failed
attempt 2: passed
```

The failed attempt is marked:

```json
{
  "flaky": true,
  "flake_reason": "passed_on_retry"
}
```

The passing record remains a passing record.

## Pass on the same SHA

A test may also be executed more than once against the same commit without
being represented as numbered retry attempts.

Example:

```text
SHA: abc123

execution A:
test_cart = failed

execution B:
test_cart = passed
```

The failure is marked:

```json
{
  "flaky": true,
  "flake_reason": "passed_on_same_sha"
}
```

Because identical code produced both a pass and a failure, TestBudget treats
the failure as nondeterministic.

## Different SHA does not count

This is not considered flaky:

```text
abc123:
test_cart = failed

def456:
test_cart = passed
```

The passing result belongs to different code.

The failure on `abc123` therefore remains a real historical failure.

## Different test does not count

A pass must have the same `test_id`.

A passing login test does not make a failing checkout test flaky even when
both were executed on the same SHA.

## Derived data

Flake information is not added to:

```text
history/results.jsonl
```

The JSONL history remains the canonical source of observed facts.

Flake classification is calculated when history is analyzed.

This keeps the committed history reproducible and avoids rewriting historical
records as the flake policy evolves.

## Using the filter

```python
from testbudget.flakes import (
    mark_flaky_failures,
)

marked = mark_flaky_failures(
    results
)
```

Each returned result contains:

```text
flaky
flake_reason
```

For example:

```json
{
  "sha": "abc123",
  "test_id": "tests/test_cart.py::test_cart",
  "status": "failed",
  "duration_s": 1.4,
  "attempt": 1,
  "flaky": true,
  "flake_reason": "passed_on_retry"
}
```

The input records are not modified.

## Filtering real failures

Evaluation code can use:

```python
from testbudget.flakes import (
    filter_non_flaky_failures,
)

failures = filter_non_flaky_failures(
    results
)
```

This returns only failures that remain after flake filtering.

Member 2's data-check and temporal replay can use this helper before
calculating failing-run counts and catch rate.

## Playwright retry records

The Playwright adapter may already collapse a retried test into one final
logical result.

For example:

```json
{
  "status": "passed",
  "attempt": 2
}
```

Such a record is not a historical failure, so it is naturally excluded by
`filter_non_flaky_failures`.

## Failure cases

The flake filter rejects malformed history, including:

- missing required fields;
- empty SHA values;
- empty test IDs;
- unsupported statuses;
- negative durations;
- non-positive attempt numbers.

Invalid history is rejected rather than silently changing evaluation
results.