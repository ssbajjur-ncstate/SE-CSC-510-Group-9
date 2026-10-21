# AI disclosure

This page lists which AI tools were used on TestBudget, what they were used for, and how a human checked the output.

## Tools used

| Tool | Model | Used by | Used for |
|---|---|---|---|
| Claude (claude.ai chat) | Claude Sonnet 5.5 | Namrata | First drafts of the link modules (`testbudget/links/`), the report command, their tests, git and GitHub CLI guidance, and drafts of CONTRIBUTING.md and this page |
| ChatGPT | TODO: model name | Namrata | TODO: what it was used for |
| TODO: teammate tools | TODO | TODO | TODO: ask each member and list them here |

## What was AI-assisted in Namrata's track

- `testbudget/links/writer.py`, `imports.py`, `cofail.py`, `pins.py`, `routes.py` and `report.py`
- The matching tests under `tests/test_links_*.py`
- The `links --report` subcommand in `testbudget/cli.py`
- The PR and issue templates, and the drafts of CONTRIBUTING.md and this page

## Prompts and plans

TODO: link the prompt transcripts or agent plan files that are in the repository. To find them, run:

```bash
git ls-files | grep -i -E "prompt|plan|transcript|agent"
```

## How a human checked the AI's output

Every AI-written change followed the same rules: it was run locally with `python -m pytest -q` before being committed, and it went through a pull request that another member reviews before merge.

Specific examples:

1. **Bug found by running it.** The first version of `summarize_links` crashed with `AttributeError: 'str' object has no attribute 'get'` when run against the older `fixtures/test_links.json`, whose entries are plain strings, not objects. This was found by running `python -m testbudget.cli links --report` by hand. The fix, and tests for it, are in the commits "fix(links): make report tolerate legacy string entries and non-object JSON" and "test(links): cover legacy entries and non-object JSON" in PR #46.
2. **Environment check.** The project requires Python 3.10 or newer, but the local virtual environment was 3.9. This was noticed when `pip install -e` failed, and the new code was checked with the existing 20 tests plus the new ones under the local interpreter.
3. **Assumptions flagged, not hidden.** The format of the `pins` section in `testbudget.yml` (a mapping from test ID to a list of files) was an assumption in the AI-written code and is marked in the PR for the owner of `testbudget.yml` to confirm.
4. **Reviewer changes:** TODO: after a teammate reviews PR #45 or #46, link one review comment or commit where a reviewer changed or questioned AI-written code.

## Limits

AI-written code can be confidently wrong. We treat it like code from any other contributor: it needs tests, a reviewer, and a passing CI run before it reaches `main`.
