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

## Publish to PyPI with a Trusted Publisher (from #64)

v0.1.0 is tagged and archived on Zenodo, but the package is not on PyPI yet.

- Needs: a PyPI project with a Trusted Publisher pointing at this repository, and a release workflow that builds the sdist and wheel and publishes on a version tag.
- Done when: `pip install testbudget` installs the tagged version, and the README shows a PyPI version badge.
