# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- Added docs/eval-protocol.md with the M0 hypothesis, baselines and metrics.
- Added committed JSONL history files and SQLite history rebuilding.
- Added migration from prototype SQLite history to committed JSONL history.
- Added pytest xunit1/xunit2 history parsing and plan-driven test execution.
- Added Playwright JUnit parsing, retry deduplication, and per-file plan invocations.

### Added

- `pyproject.toml` with a `testbudget` console script and a `dev` extra; install with `pip install -e ".[dev]"`.

