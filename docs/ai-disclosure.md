# AI disclosure

This page lists which AI tools were used on TestBudget, what they were used for, and how a human checked the output.

## Tools used

All four members used the same two tools: Claude and ChatGPT, through their normal chat apps. Exact model versions were not recorded for ChatGPT. The teammate rows below were reported by Namrata, and each member can correct their own row by pull request.

| Tool | Model | Used by | Used for |
|---|---|---|---|
| Claude (claude.ai chat) | Claude Sonnet 5.5 | Namrata | First drafts of the link modules (`testbudget/links/`), the `links --report` command, their tests, git and GitHub CLI guidance, and drafts of `CONTRIBUTING.md` and this page |
| ChatGPT | Default model in the ChatGPT app (exact version not recorded) | Namrata | Additional help alongside Claude |
| Claude and ChatGPT | As above | Vedantt | Coding and project help (reported by Namrata) |
| Claude and ChatGPT | As above | Saanvi | Coding and project help (reported by Namrata) |
| Claude and ChatGPT | As above | Sakshi | Coding and project help (reported by Namrata) |

## What was AI-assisted in Namrata's track

- `testbudget/links/writer.py`, `imports.py`, `cofail.py`, `pins.py`, `routes.py` and `report.py`
- The matching tests under `tests/test_links_*.py`
- The `links --report` subcommand in `testbudget/cli.py` and its tests in `tests/test_cli.py`
- The PR and issue templates under `.github/`
- Drafts of `CONTRIBUTING.md` and this page

## Prompts and plans

The AI chats for this track were held in the Claude and ChatGPT apps and are not stored as files in this repository. Prompt transcripts or agent plan files that other members committed can be found with:

```bash
git ls-files | grep -i -E "prompt|plan|transcript|agent"
```

## How a human checked the AI's output

Every AI-written change followed the same rules. It was run locally with `python -m pytest -q` before being committed, and it went through a pull request that another member reviews before merge. Reviews of PRs #45 and #46 are on those pull requests.

Specific examples:

1. **Bug found by running the code.** The first version of `summarize_links` crashed with `AttributeError: 'str' object has no attribute 'get'` when run against the older `fixtures/test_links.json`, whose entries are plain strings, not objects. This was found by running `python -m testbudget.cli links --report` by hand. The fix and its tests are in the commits "fix(links): make report tolerate legacy string entries and non-object JSON" and "test(links): cover legacy entries and non-object JSON" in PR #46.
2. **Environment check.** The project requires Python 3.10 or newer, but the local virtual environment used Python 3.9. This was noticed when `pip install -e` failed. The new code was checked with the existing 20 tests plus the new ones under the local interpreter, and a proper Python 3.10+ environment is still needed for the full install.
3. **Assumptions flagged, not hidden.** The format of the `pins` section in `testbudget.yml` (a mapping from test ID to a list of files) was an assumption in the AI-written code. It is raised as a comment on PR #45 for the owner of `testbudget.yml` to confirm.

## Limits

AI-written code can be confidently wrong. We treat it like code from any other contributor: it needs tests, a reviewer, and a passing CI run before it reaches `main`.
