# Reviewer overrides and audit mode

TestBudget normally executes only the tests selected by its budgeted plan.

Two mechanisms allow the team to collect more evidence safely:

1. an authorized reviewer can request a full-suite run;
2. audit mode can execute the full suite while preserving the plan TestBudget
   would have selected.

## Reviewer command

A reviewer can request the complete suite using:

```text
/testbudget full
```

The command is accepted only when the comment author's resolved repository
permission is:

```text
write
maintain
admin
```

The following permissions are not sufficient:

```text
read
triage
```

## Why permission checking is separate

The reviewer module does not call GitHub directly.

The GitHub integration resolves the comment author's repository permission
and passes that value to TestBudget.

For example:

```python
from testbudget.reviewer import (
    parse_reviewer_command,
)

command = parse_reviewer_command(
    "/testbudget full",
    actor_permission="write",
)
```

This keeps authorization logic deterministic and testable without requiring
network access.

## Result

A valid command returns:

```python
{
    "action": "full",
}
```

An unrelated comment returns:

```python
None
```

Unsupported TestBudget commands and unauthorized requests fail explicitly.

## Known test IDs

Reviewer-driven test IDs must already exist in TestBudget history.

Load known IDs with:

```python
from testbudget.reviewer import (
    load_known_test_ids,
)

known = load_known_test_ids("history")
```

Validate requested IDs with:

```python
from testbudget.reviewer import (
    validate_test_ids,
)

validated = validate_test_ids(
    requested_test_ids,
    known,
)
```

Unknown IDs are rejected instead of being forwarded to a test runner.

## Normal execution

Suppose TestBudget produces:

```text
selected:
A
B

skipped:
C
D
```

Normal execution is:

```text
A
B
```

## Audit mode

Audit mode preserves that plan but executes:

```text
A
B
C
D
```

The original plan remains:

```text
selected:
A
B

skipped:
C
D
```

This distinction matters because audit mode answers:

> What would TestBudget have selected, and what did the full suite actually
> reveal?

If audit mode rewrote every test as selected, that evidence would be lost.

## Building an execution policy

```python
from testbudget.audit import (
    build_execution_policy,
)

policy = build_execution_policy(
    plan,
    all_test_ids,
    audit_mode=True,
)
```

Example result:

```python
{
    "mode": "audit",
    "audit_mode": True,
    "force_full": False,
    "execute_test_ids": [
        "A",
        "B",
        "C",
        "D",
    ],
    "planned_selected_test_ids": [
        "A",
        "B",
    ],
    "planned_skipped_test_ids": [
        "C",
        "D",
    ],
}
```

## Reviewer full-suite override

After parsing:

```python
command = parse_reviewer_command(
    "/testbudget full",
    "write",
)
```

apply it using:

```python
from testbudget.audit import (
    apply_reviewer_command,
)

policy = apply_reviewer_command(
    plan,
    all_test_ids,
    command,
)
```

The resulting mode is:

```text
reviewer_full
```

and all known tests execute.

## Audit vs reviewer full

Both modes execute the complete suite, but they express different intent.

### Audit

```text
mode = audit
```

The project is deliberately collecting full-suite evidence while observing
what TestBudget would have selected.

### Reviewer full

```text
mode = reviewer_full
```

An authorized reviewer explicitly overrode budgeted selection.

Keeping the modes separate allows checks and evaluation reports to explain
why the full suite ran.

## Integration responsibility

This module does not:

- receive GitHub webhooks;
- call the GitHub permission API;
- post check runs;
- execute pytest or Playwright itself.

Those integration layers consume the command and execution-policy objects.

This separation avoids coupling policy logic to GitHub networking and keeps
the core behavior easy to test.