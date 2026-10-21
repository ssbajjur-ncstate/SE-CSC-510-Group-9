# Playwright adapter

TestBudget's Playwright adapter converts Playwright test results and
TestBudget plans into the shared TestBudget formats.

It provides two main capabilities:

1. normalize Playwright JUnit results into TestBudget history;
2. group selected Playwright tests into per-file invocation lists.

## Test identity

Playwright tests use:

```text
file › title
```

Example:

```text
tests/checkout.spec.ts › checkout rejects an invalid card
```

This identity is shared by history, links, ranking, replay, and execution.

## Generating Playwright JUnit

Playwright can write a JUnit report using:

```bash
PLAYWRIGHT_JUNIT_OUTPUT_NAME=results.xml \
npx playwright test --reporter=junit
```

For TestBudget retry information, configure the JUnit reporter with retry
details enabled.

For example:

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  reporter: [
    [
      'junit',
      {
        outputFile: 'results.xml',
        includeRetries: true,
      },
    ],
  ],
});
```

The same behavior can also be enabled through Playwright's JUnit retry
environment option.

## Parsing JUnit

```python
from testbudget.adapters.playwright_adapter import (
    parse_playwright_junit,
)

results = parse_playwright_junit(
    "results.xml"
)
```

A normal result looks like:

```json
{
  "test_id": "tests/checkout.spec.ts › checkout succeeds",
  "status": "passed",
  "duration_s": 1.2,
  "attempt": 1
}
```

## Status normalization

TestBudget uses:

```text
passed
failed
skipped
```

JUnit failure and error records become:

```text
failed
```

Skipped records become:

```text
skipped
```

## Retry deduplication

A retried Playwright test counts as one logical test.

Suppose:

```text
attempt 1: failed, 1.4 seconds
attempt 2: passed, 0.8 seconds
```

TestBudget stores:

```json
{
  "status": "passed",
  "duration_s": 0.8,
  "attempt": 2
}
```

The important points are:

- the test appears once;
- the final outcome is stored;
- the final attempt's duration is stored;
- the attempt number preserves the fact that retrying occurred.

The later flake filter uses retry information to classify flaky failures.

## Older Playwright classnames

Some Playwright JUnit versions may include source locations:

```text
tests/login.spec.ts:13:5
```

TestBudget removes the unstable line and column suffix:

```text
tests/login.spec.ts
```

This keeps the test ID stable when source lines move.

## Missing duration

If JUnit does not provide `time`, TestBudget records:

```json
"duration_s": 0.0
```

instead of dropping the result.

## Building Playwright invocations

Read selected Playwright tests from `plan.json`:

```python
from testbudget.adapters.playwright_adapter import (
    build_playwright_invocations,
)

invocations = build_playwright_invocations(
    "plan.json"
)
```

Suppose the plan selects:

```text
tests/checkout.spec.ts › checkout succeeds
tests/payment.spec.ts › payment succeeds
tests/checkout.spec.ts › checkout rejects card
```

TestBudget returns:

```python
[
    {
        "file": "tests/checkout.spec.ts",
        "test_ids": [
            "tests/checkout.spec.ts › checkout succeeds",
            "tests/checkout.spec.ts › checkout rejects card",
        ],
        "titles": [
            "checkout succeeds",
            "checkout rejects card",
        ],
    },
    {
        "file": "tests/payment.spec.ts",
        "test_ids": [
            "tests/payment.spec.ts › payment succeeds",
        ],
        "titles": [
            "payment succeeds",
        ],
    },
]
```

## Why per-file invocation?

Playwright normally executes test files in parallel and does not guarantee
execution order across files.

TestBudget therefore does not rely on passing one ordered list of test IDs to
Playwright.

Instead, the adapter produces per-file invocation groups that the integration
layer can execute deliberately.

## Mixed-framework plans

Plans may contain pytest and Playwright tests.

Pytest IDs use:

```text
path::name
```

Playwright IDs use:

```text
file › title
```

The Playwright adapter ignores pytest IDs.

## Invalid input

The adapter rejects:

- missing JUnit files;
- malformed XML;
- testcases without usable files;
- testcases without titles;
- invalid durations;
- missing plan files;
- malformed plan JSON;
- plans without a selected list.