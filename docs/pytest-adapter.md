# Pytest adapter

TestBudget's pytest adapter connects pytest execution to the shared
TestBudget history and plan formats.

It provides two capabilities:

1. normalize pytest JUnit output into TestBudget history records;
2. execute only the pytest tests selected by `plan.json`, in plan order.

## Test identity

Pytest tests use the TestBudget identity:

```text
path::name
```

Example:

```text
tests/test_checkout.py::test_checkout_success
```

This identity is shared by history, links, ranking, replay, and execution.

## Parsing pytest JUnit

Generate a pytest JUnit report:

```bash
python -m pytest \
  --junitxml=test-results.xml
```

Parse it:

```python
from testbudget.adapters.pytest_adapter import parse_pytest_junit

results = parse_pytest_junit("test-results.xml")
```

A result looks like:

```json
{
  "test_id": "tests/test_checkout.py::test_checkout_success",
  "status": "passed",
  "duration_s": 1.21,
  "attempt": 1
}
```

The adapter accepts pytest xunit1 and xunit2 reports.

## xunit1

xunit1 commonly provides a `file` attribute directly.

For example:

```xml
<testcase
    classname="tests.test_checkout"
    name="test_checkout_success"
    file="tests/test_checkout.py"
    time="1.21"
/>
```

TestBudget uses the explicit file path.

## xunit2

xunit2 may omit `file`.

In that case TestBudget derives the path from the JUnit `classname`.

For example:

```text
tests.test_checkout
```

becomes:

```text
tests/test_checkout.py
```

A class-based classname such as:

```text
tests.test_checkout.TestCheckout
```

also maps to:

```text
tests/test_checkout.py
```

## Status normalization

TestBudget uses three result states:

```text
passed
failed
skipped
```

JUnit `<failure>` and `<error>` are both recorded as:

```text
failed
```

JUnit `<skipped>` becomes:

```text
skipped
```

A testcase with none of those children is:

```text
passed
```

## Missing duration

JUnit producers may omit the `time` attribute.

TestBudget stores such results as:

```json
"duration_s": 0.0
```

instead of discarding the test result.

## Retry attempts

If the same test appears repeatedly in one JUnit report, TestBudget assigns
attempt numbers:

```text
attempt 1
attempt 2
attempt 3
```

The flake-filter stage can later use this information to detect failures that
pass on retry.

## Running a TestBudget plan

Load the pytest adapter as a plugin:

```bash
python -m pytest \
  -p testbudget.adapters.pytest_adapter \
  --testbudget-plan plan.json
```

Suppose pytest normally collects:

```text
test_alpha
test_beta
test_gamma
```

and `plan.json` selects:

```json
{
  "selected": [
    {
      "test_id": "tests/test_example.py::test_gamma"
    },
    {
      "test_id": "tests/test_example.py::test_alpha"
    }
  ]
}
```

TestBudget changes collection to:

```text
test_gamma
test_alpha
```

`test_beta` is reported as deselected.

This means TestBudget controls both:

- which pytest tests run;
- the order in which they run.

## Mixed-framework plans

A TestBudget plan can contain tests from multiple frameworks.

The pytest adapter only consumes pytest IDs using:

```text
path::name
```

Playwright tests use a different identity format and are ignored by the
pytest adapter.

## Running without TestBudget

If `--testbudget-plan` is not supplied, the plugin leaves pytest collection
unchanged.

Normal pytest execution is preserved.

## Invalid plans

The adapter rejects:

- missing plan files;
- malformed JSON;
- plans without a `selected` list;
- selected entries without valid `test_id` values.

This avoids silently running an unintended set of tests.

## Plugin helper naming

Functions beginning with `pytest_` are reserved for pytest hooks when a
module is loaded as a plugin.

Internal TestBudget helper functions therefore avoid that prefix unless they
implement a real pytest hook.

This prevents pluggy from attempting to register ordinary helper functions
as pytest hooks.