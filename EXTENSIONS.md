# Extension Tracks

## Risk-Aware Test-Budget Calibration

**Purpose:** Allocate testing effort according to risk while respecting a configurable test budget.

**Approach:**
- Use historical test-run data when available.
- Estimate budget fractions for each risk level.
- Apply configurable minimum and maximum limits.
- Inherit budget settings for risk levels with sparse data.
- Validate the calibration using replay data and automated tests.

**Current limitation:** Historical run data is limited, so calibration decisions should be treated as provisional until sufficient evidence is available.
