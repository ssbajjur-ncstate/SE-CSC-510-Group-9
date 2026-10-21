# TestBudget

[![CI](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/actions/workflows/ci.yml)
[![Docs](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/actions/workflows/docs.yml)
[![codecov](https://codecov.io/gh/ssbajjur-ncstate/SE-CSC-510-Group-9/branch/main/graph/badge.svg)](https://codecov.io/gh/ssbajjur-ncstate/SE-CSC-510-Group-9)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/types-mypy-blue.svg)](https://mypy-lang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What

TestBudget decides which of a repository's existing tests run on a pull request, in what order, and for how long. It learns from the repository's own CI history: no new tests, no coverage instrumentation, no external service.

## Why

Full test suites grow faster than CI budgets. Most pull requests touch a small part of the code, yet every run pays for the whole suite. TestBudget spends a time budget on the tests most likely to fail for this change, and never silently drops the tests that must always run.

## How

1. **History.** JUnit reports are ingested into committed JSONL history (`history/runs.jsonl`, `history/results.jsonl`) and a local SQLite cache.
2. **Links.** `testbudget links --build` maps tests to source files from Python imports, Playwright routes, co-failures in history, and pins in `testbudget.yml`, and writes `links.json`.
3. **Risk map.** Each changed file carries a failure weight from history; the change set's score is bucketed into `low`, `medium` or `high` risk.
4. **Ranker.** Tests are scored by link to the change, past failures and runtime.
5. **Hard rules.** Pinned tests go first, then tests whose own file changed, then recent failures. Tests skipped too often (rotation limit) are forced in, and lockfile, CI-config, `.env`, tag and release changes force the full suite.
6. **Budget cut.** Forced tests count against the budget but are never cut; the rest fill the budget in rank order.
7. **plan.json.** The plan records the SHA, risk level, budget, selected tests with reasons, skipped tests with skip reason and skip debt, and an estimated catch rate.
8. **Feedback.** Replays of history give a catch rate per risk level and budget; `testbudget calibrate` turns them into per-level budgets in `testbudget.yml`.

## Quickstart

```bash
git clone https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9.git
cd SE-CSC-510-Group-9
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"

testbudget init --db tb.db
testbudget ingest fixtures/sample_junit.xml --db tb.db --changed-file src/checkout.py
testbudget links --build --history history --output links.json
testbudget links --report --links links.json
testbudget plan --changed src/checkout.py --budget 2 --db tb.db   --links fixtures/test_links.json --history history --sha demo --output plan.json
testbudget calibrate --replay fixtures/replay_synthetic.csv --output testbudget.yml
```

## Development

```bash
python -m pytest
ruff check .
ruff format --check .
mypy
```

See [INSTALL.md](INSTALL.md), [CONTRIBUTING.md](CONTRIBUTING.md) and the [documentation](docs/index.md).

## M0 result

See [docs/m0-decision.md](docs/m0-decision.md).

## License

MIT. See [LICENSE](LICENSE). To cite TestBudget, see [CITATION.cff](CITATION.cff).
