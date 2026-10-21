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

- Link sources for the ranker: `links.json` writer, Python import links, co-failure links and pinned links (`testbudget/links/`).
- Pre-commit hooks (ruff, ruff-format, pytest), ruff `W` and `UP` rules, and strict mypy for `ranker`, `selector` and `riskmap`.
- Risk map (`testbudget/riskmap.py`): file failure weights shrunk toward the global failure rate, a change risk score, and quantile risk levels.
- `testbudget links --report` command summarising a links file by source.
- `THIRD_PARTY_LIBRARIES.md` listing build and dev dependencies with their licences.
- Budget calibration (`testbudget/calibrate.py`): per-risk-level budget fractions from the replay CSV, with floor, ceiling and upward inheritance for sparse levels, written into a generated block of `testbudget.yml`.
