# Dogfooding TestBudget

TestBudget is tested on real pull requests before release.

The dogfooding setup uses three repositories:

1. the TestBudget repository itself;
2. the MealSlot fork as a larger external repository;
3. a small fixture repository kept ready for live demonstrations.

## TestBudget repository

The repository's TestBudget workflow follows the audit-mode workflow:

1. generate the TestBudget plan before tests;
2. run the complete test suite;
3. generate JUnit output;
4. ingest the result after execution.

Running the complete suite during dogfooding allows the team to compare the
tests TestBudget would have selected against the failures found by the full
suite.

The live workflow and pull-request evidence are recorded in the associated
dogfooding issue.

## Local verification

Each team member should verify that TestBudget can produce a plan locally.

From a clean clone:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"