# TestBudget

TestBudget is a prototype GitHub-oriented test planning tool that uses a repository's own test history to prioritize which existing tests should run for a code change under a time budget.

## Current Prototype

The current vertical slice supports:

- JUnit XML ingestion
- SQLite-backed historical test statistics
- baseline ranking using changed-file relevance, historical failures, and runtime
- selection of tests within a supplied time budget
- a command-line workflow for init, ingest, and plan

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If requirements.txt is not used on your machine, install pytest directly for development:

```bash
python -m pip install pytest
```

## Run Tests

```bash
python -m pytest -q
```

## CLI Workflow

### 1. Initialize local history

```bash
python -m testbudget.cli init
```

### 2. Ingest a JUnit report

```bash
python -m testbudget.cli ingest fixtures/sample_junit.xml \
 --changed-file src/checkout.py
```

### 3. Generate a test plan

```bash
python -m testbudget.cli plan \
 --changed src/checkout.py \
 --budget 10
```

The plan shows ranked tests, selected tests, skipped tests, reasons, and estimated runtime.

## Prototype Pipeline

JUnit history
   -> SQLite statistics
   -> changed-file links
   -> baseline risk ranking
   -> budget selection
   -> CLI test plan

## Current Limitations

This is the first executable prototype, not the final TestBudget algorithm.

Currently:

- CI history is represented by a sample JUnit fixture
- file-to-test relationships are manually provided in fixtures/test_links.json
- the execution budget is supplied by the user
- GitHub Actions history backfill is not yet implemented
- automatic import, route, and co-failure linking are not yet implemented
- replay-based budget calibration is not yet implemented
- GitHub PR checks and reviewer overrides are not yet implemented

These are planned later milestones.

