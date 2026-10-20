def select_with_budget(ranked_tests, budget):
    """
    Select ranked tests while staying within the supplied time budget.
    Tests are considered in ranking order.
    If a test does not fit in the remaining budget, it is skipped.
    Later shorter tests may still be selected if they fit.
    """
    if budget < 0:
        raise ValueError("Budget cannot be negative")

    selected = []
    skipped = []
    used_time = 0.0

    for test in ranked_tests:
        duration = float(test.get("duration", 0.0))
        if used_time + duration <= budget:
            selected.append(test)
            used_time += duration
        else:
            skipped_test = dict(test)
            skipped_test["skip_reason"] = "budget exhausted"
            skipped.append(skipped_test)

    return {
        "selected": selected,
        "skipped": skipped,
        "estimated_runtime": round(used_time, 3),
        "budget": float(budget),
    }
