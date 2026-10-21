# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- Added docs/eval-protocol.md with the M0 hypothesis, baselines and metrics.
- Added docs/eval-protocol.md with the M0 hypothesis, baselines and metrics.
- Add pull request template and issue templates (feature, bug, test-failure).
- Added committed JSONL history files and SQLite history rebuilding.
- Added migration from prototype SQLite history to committed JSONL history.
- Added pytest xunit1/xunit2 history parsing and plan-driven test execution.
- Added Playwright JUnit parsing, retry deduplication, and per-file plan invocations.
- Added derived flake filtering for retry passes and same-SHA pass/fail results.
- Added authorized `/testbudget full` reviewer overrides and audit-mode execution policy.

### Added

- `pyproject.toml` with a `testbudget` console script and a `dev` extra; install with `pip install -e ".[dev]"`.
- Pre-commit hooks (ruff, ruff-format, pytest), ruff `W` and `UP` rules, and strict mypy for `ranker`, `selector` and `riskmap`.
- Risk map (`testbudget/riskmap.py`): file failure weights shrunk toward the global failure rate, a change risk score, and quantile risk levels.
- `testbudget links --report` command summarising a links file by source.
- `THIRD_PARTY_LIBRARIES.md` listing build and dev dependencies with their licences.
- Baseline orderings for the replay evaluation, as defined in docs/eval-protocol.md: recently failed first, most often failed first, most recently modified first, and import-only (testbudget/baselines.py).
- Budget calibration (`testbudget/calibrate.py`): per-risk-level budget fractions from the replay CSV, with floor, ceiling and upward inheritance for sparse levels, written into a generated block of `testbudget.yml`.
