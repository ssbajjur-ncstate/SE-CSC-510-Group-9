# Contributing to TestBudget

Thanks for helping. This guide covers the coding standards, the workflow every change goes through, and how to extend TestBudget without breaking it.

## Setup

```bash
git clone https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9.git
cd SE-CSC-510-Group-9
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"          # requires Python 3.10 or newer
python -m pytest -q
```

## Workflow (every change)

1. **Issue first.** Open an issue using a template in `.github/ISSUE_TEMPLATE/`. Title it with the milestone tag, for example `[M1] Rotation limit rule`. Add a `milestone:` label and a `type:` label, assign yourself, and add it to the project board.
2. **Discuss.** Before the issue is closed, someone other than the author must comment on it. If the discussion happened in Discord, paste a one-line summary.
3. **Branch.** Work on `feat/<area>` or `fix/<area>`, branched from an up-to-date `main`.
4. **Small commits.** Commit after each function, test or doc section. Use a prefix: `feat`, `fix`, `test`, `docs`, `chore`, `build`.
5. **Tests in the same PR.** Include at least one failure-case test per feature (bad input, empty history, missing file).
6. **Changelog.** Add one line under `## [Unreleased]` in `CHANGELOG.md`.
7. **Open a PR** using the template, with `Closes #N`.
8. **Review.** Another member reviews, with at least one substantive comment. Never review or merge your own PR.
9. **Merge** with a merge commit or rebase-merge. Do not squash, because small commits are part of the project record.
10. **Failing CI** means a new issue with the `type:test-failure` label and the log excerpt, fixed by a PR that closes it.

## Coding standards

- Python 3.10 or newer. Use type hints on public functions.
- Every public function has a docstring that says what it does in one or two lines. The docs site is generated from these.
- Style and type checks use the `ruff` and `mypy` settings in `pyproject.toml`. Run them before pushing.
- Tests live in `tests/`, named `test_<module>.py`, with functions named `test_<behaviour>`. Use `tmp_path` for files, not the real repo.
- Do not commit `.db` files, `.venv`, `node_modules` or secrets.
- Follow the shared data contracts: `links.json`, `plan.json`, `history/*.jsonl` and `testbudget.yml`. If a contract needs to change, open an issue and tell the members whose code reads it first.

## Extension points

TestBudget has four places designed for extension:

| Extension point | What you add | Where it lives |
|---|---|---|
| Link source | A function that returns links between tests and files | `testbudget/links/` |
| Adapter | A parser for another test runner's output | `testbudget/adapters/` |
| Policy rule | A hard rule applied before the budget cut | `testbudget/rules.py` |
| Dashboard page | A page on the static results dashboard | the dashboard app |

### Worked example: adding a link source

A link source is a function that returns `{test_id: [{"file", "source", "weight"}]}`. Here we add a `sibling` source: `tests/test_foo.py::test_x` is linked to `src/foo.py`, because tests are usually named after the file they test.

**1. Register the source name** in `testbudget/links/writer.py`. Without this, `validate_links` rejects the new links:

```python
VALID_SOURCES = {"import", "route", "cofail", "pin", "sibling"}
```

**2. Write the source** in `testbudget/links/sibling.py`:

```python
"""Sibling links: tests/test_foo.py is linked to foo.py."""
from __future__ import annotations

from pathlib import Path


def build_sibling_links(root: Path, test_ids: list[str]) -> dict[str, list[dict]]:
    """Link each test to a source file named after its test file, if one exists."""
    links: dict[str, list[dict]] = {}
    for test_id in test_ids:
        test_file = test_id.split("::")[0]
        name = Path(test_file).name.removeprefix("test_")
        matches = sorted(p for p in root.rglob(name) if "tests" not in p.parts)
        links[test_id] = [
            {"file": m.relative_to(root).as_posix(), "source": "sibling", "weight": 0.5}
            for m in matches
        ]
    return links
```

**3. Test it, including a failure case**, in `tests/test_links_sibling.py`:

```python
from testbudget.links.sibling import build_sibling_links


def test_links_test_to_matching_source(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x = 1\n")
    links = build_sibling_links(tmp_path, ["tests/test_foo.py::test_x"])
    assert links["tests/test_foo.py::test_x"][0]["file"] == "src/foo.py"


def test_no_matching_source_gives_empty_list(tmp_path):
    links = build_sibling_links(tmp_path, ["tests/test_foo.py::test_x"])
    assert links["tests/test_foo.py::test_x"] == []
```

**4. Merge it** with the other sources using `merge_links` from `testbudget/links/writer.py`, then write the result with `write_links`.

**5. Do the paperwork:** issue, branch, changelog line, PR, review.

### Tips for extending without breaking things

- Run the full test suite before pushing, not only your new tests.
- Keep new link weights relative to the existing ones (import links use 1.0, pins use 10.0).
- Return an empty list or dictionary for missing input rather than raising, unless bad input is a real error. In that case raise `ValueError` with a message that names the file.
- Do not change the shape of `links.json`. Add a new `source` value instead.
