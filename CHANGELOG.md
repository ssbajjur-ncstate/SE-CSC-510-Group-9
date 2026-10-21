# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- Added docs/eval-protocol.md with the M0 hypothesis, baselines and metrics.
- Add pull request template and issue templates (feature, bug, test-failure).
- Added committed JSONL history files and SQLite history rebuilding.

### Added

- `pyproject.toml` with a `testbudget` console script and a `dev` extra; install with `pip install -e ".[dev]"`.
- `THIRD_PARTY_LIBRARIES.md` listing build and dev dependencies with their licences.
- Nightly attribution (`testbudget/feedback.py`): PRs whose plan skipped a test that failed on nightly, ranked by link strength, with a miss record per missed test.
