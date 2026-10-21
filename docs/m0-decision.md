# M0 Spiral Review Decision

## Evidence
The evaluation protocol sets a target of catching at least 85% of historical failing runs using a test budget of 30% of full-suite runtime. The M0a data check found no recorded historical run results, so the hypothesis cannot yet be evaluated.

## Decision: Re-plan
Do not claim success or failure until sufficient historical data is available.

## Next steps
1. Collect or reconstruct historical CI runs and test results.
2. Separate real failures from synthetic failures.
3. Run the predefined temporal evaluation and baseline comparisons.
4. Record the measured results and final decision.

## Status
The evaluation protocol is documented. Empirical validation remains pending.
## Current evidence
The evaluation protocol defines an 85% catch-rate target at a 30% test-time budget and compares TestBudget against baseline methods.

The available M0a data check found no recorded historical runs/results. Therefore, the catch-rate hypothesis and baseline comparison cannot yet be evaluated.

## Decision: Re-plan
Do not claim the hypothesis passed or failed without sufficient real historical data.

## Next actions
1. Collect or reconstruct historical CI runs and test results.
2. Separate real failures from synthetic/planted failures.
3. Run the predefined temporal evaluation and baseline comparisons.
4. Record the results, data limitations, and decision in the M0 issue.

## Status
The evaluation protocol is documented; empirical validation remains pending.

## Temporal replay implementation

The M0 temporal replay harness is now implemented in
`testbudget/replay.py`.

It:

- replays historical runs chronologically;
- uses only history that existed before the run being evaluated;
- evaluates every method at 30% of full-suite execution time;
- compares TestBudget with original order, seeded random order,
  pytest-ranking heuristics, and import-only ordering;
- reports catch rate, APFDc, and median time to first failure;
- writes reproducible results to `data/eval_results.csv`;
- is reproducible with `make eval`.

## Current M0 result

The currently committed evaluation fixture does not contain enough
historically failing runs to evaluate the project's headline claim.

The evaluation protocol requires approximately 10 failing runs per risk level
before the result is considered meaningful. The current fixture contains fewer
than that threshold.

Therefore the current M0 decision is:

**RE-PLAN / INSUFFICIENT DATA**

The replay infrastructure is working and reproducible, but the project does
not claim that the 85% catch-rate target has been demonstrated on the current
committed dataset.

A larger real CI-history snapshot, such as the planned MealSlot back-fill,
is required before making that empirical claim.

Synthetic or fixture replay results are kept separate from claims about real
repository performance.

