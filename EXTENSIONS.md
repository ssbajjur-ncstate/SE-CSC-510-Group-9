# Project 3 extensions

## Replay on a second language ecosystem (Saanvi's track)

Run the replay and `make eval` on a Playwright suite's CI history, not only pytest.

- Needs: a Playwright JUnit adapter (Member 4's track) and a back-filled history from a public Playwright repository.
- Suggested M0 claim: on that history, TestBudget catches at least 85% of failing runs at 30% of suite time, and beats the original-order and random baselines.
- Failure condition: fewer than about 10 real failing runs in the history, or a catch rate below the best baseline.

## Member 2 — Risk-aware test-budget calibration

This track investigates how to choose a smaller, risk-aware test budget while
preserving the ability to detect failing runs. It summarizes available test
history, evaluates test-selection strategies against baseline approaches, and
reports when the available evidence is insufficient to justify a budget
decision. Synthetic replay data is kept separate from observed historical data.
