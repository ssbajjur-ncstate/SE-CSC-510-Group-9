# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- Added docs/eval-protocol.md with the M0 hypothesis, baselines and metrics.
- Added docs/eval-protocol.md with the M0 hypothesis, baselines and metrics.
- Add pull request template and issue templates (feature, bug, test-failure).
- Added committed JSONL history files and SQLite history rebuilding.

### Added

- `pyproject.toml` with a `testbudget` console script and a `dev` extra; install with `pip install -e ".[dev]"`.

- `testbudget links --report` command summarising a links file by source.
- `THIRD_PARTY_LIBRARIES.md` listing build and dev dependencies with their licences.
- GitHub check-run payload builder with 50-annotation paging, token check and update-in-place publishing (`testbudget/github/checks.py`), with a fixture plan in `fixtures/plan.json`.
- Budget calibration (`testbudget/calibrate.py`): per-risk-level budget fractions from the replay CSV, with floor, ceiling and upward inheritance for sparse levels, written into a generated block of `testbudget.yml`.
