# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- `testbudget migrate --db <sqlite>` moves prototype SQLite history into JSONL history.
- `testbudget plan --audit`, `--reviewer-comment` and `--policy-output` expose audit mode and `/testbudget full` overrides.
- Rewrote README (what, why, how, quickstart), added badges, Codecov upload, CITATION.cff and .zenodo.json.
- `testbudget calibrate --replay <csv> [--output testbudget.yml]` writes calibrated per-risk-level budgets.
- `testbudget links --build [--output links.json]` builds the link map from imports, routes, co-failures and pins.
- `testbudget plan` applies hard rules before the budget cut and writes plan.json with `--output` and `--config`.
- Fixed duplicate `external-caller` job that broke the testbudget workflow on main.
- Added docs/eval-protocol.md with the M0 hypothesis, baselines and metrics.
- Add pull request template and issue templates (feature, bug, test-failure).
- Added committed JSONL history files and SQLite history rebuilding.
- Added LICENSE (MIT), CODE-OF-CONDUCT.md, INSTALL.md and EXTENSIONS.md.
- Added migration from prototype SQLite history to committed JSONL history.
- Added pytest xunit1/xunit2 history parsing and plan-driven test execution.
- Added Playwright JUnit parsing, retry deduplication, and per-file plan invocations.
- Added derived flake filtering for retry passes and same-SHA pass/fail results.

- Added authorized `/testbudget full` reviewer overrides and audit-mode execution policy.


### Added

- Composite GitHub Action (`action.yml`) with `plan` and `ingest` modes and a cached history database, plus a workflow that runs it on this repository's own PRs.
- mkdocs documentation site: project story, a links tutorial and an API reference generated from docstrings, deployed to GitHub Pages.
- `pyproject.toml` with a `testbudget` console script and a `dev` extra; install with `pip install -e ".[dev]"`.


- Link sources for the ranker: `links.json` writer, Python import links, co-failure links and pinned links (`testbudget/links/`).

- Route links: resolve Playwright `page.goto` paths to Next.js route files (`testbudget/links/routes.py`).
- 
- `CONTRIBUTING.md` with workflow, coding standards and a worked link-source example, and `docs/ai-disclosure.md`.
- Pre-commit hooks (ruff, ruff-format, pytest), ruff `W` and `UP` rules, and strict mypy for `ranker`, `selector` and `riskmap`.
- Risk map (`testbudget/riskmap.py`): file failure weights shrunk toward the global failure rate, a change risk score, and quantile risk levels.
- `testbudget links --report` command summarising a links file by source.
- `THIRD_PARTY_LIBRARIES.md` listing build and dev dependencies with their licences.
- GitHub check-run payload builder with 50-annotation paging, token check and update-in-place publishing (`testbudget/github/checks.py`), with a fixture plan in `fixtures/plan.json`.

- Nightly attribution (`testbudget/feedback.py`): PRs whose plan skipped a test that failed on nightly, ranked by link strength, with a miss record per missed test.

- Hard rules (`testbudget/rules.py`): pinned tests first, changed test files next, recent failures next, a rotation limit from skip debt, and a full-suite trigger for lockfile, CI config, `.env`, tag and release changes.

- Baseline orderings for the replay evaluation, as defined in docs/eval-protocol.md: recently failed first, most often failed first, most recently modified first, and import-only (testbudget/baselines.py).
- Budget calibration (`testbudget/calibrate.py`): per-risk-level budget fractions from the replay CSV, with floor, ceiling and upward inheritance for sparse levels, written into a generated block of `testbudget.yml`.

- Documented the M0 evaluation decision and outstanding data requirements.

- Added guidance for preparing releases and configuring Zenodo archiving.
- Added a retrospective for PR #6.
- Document main-branch protection and pull-request workflow for M1.
- Documented the risk-aware test-budget calibration track in EXTENSIONS.md.
