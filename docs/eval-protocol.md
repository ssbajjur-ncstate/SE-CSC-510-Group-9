# TestBudget evaluation protocol

## 1. Hypothesis

TestBudget, run with a time budget of 30% of the full suite's duration, catches at least 85% of historically failing runs. A run is caught if at least one test that failed in that run is in the selected set.

This claim is written before any result exists. Results are reported as they come out, including if they miss.

## 2. Baselines

TestBudget is compared with these orderings, all given the same history and the same budget:

1. Original order: tests in the order the suite runs them today.
2. Random: a seeded random order, repeated over several seeds and averaged.
3. pytest-ranking, three heuristics: recently failed first, most often failed first, and most recently modified first.
4. Import-only: tests whose files import a changed file, with no history.

## 3. Metrics

- Catch rate at 30% of suite time: share of failing runs where a failing test falls inside the selected set, with selected tests totalling at most 30% of the full suite duration.
- APFDc: cost-aware average percentage of faults detected, where each test costs its duration.
- Time to first failure: seconds of test time before the first failing test runs in a failing run.

Each metric is reported per method and per risk level.

## 4. Temporal split
## 5. Failing runs and flakes
## 6. Failure conditions
## 7. Data sources