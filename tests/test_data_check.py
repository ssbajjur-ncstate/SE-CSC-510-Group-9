from scripts.data_check import check_history


def test_empty_history_reports_zero_runs(tmp_path):
    rows = check_history(tmp_path)

    summary = next(row for row in rows if row["category"] == "run_summary")

    assert summary["total"] == 0
    assert summary["failing_runs"] == 0


def test_counts_runs_and_failing_runs(tmp_path):
    history_dir = tmp_path / "history"
    history_dir.mkdir()

    (history_dir / "runs.jsonl").write_text(
        '{"sha":"abc123","timestamp":"2026-10-20T10:00:00Z",'
        '"branch":"main","changed_files":["src/cart.py"]}\n'
        '{"sha":"def456","timestamp":"2026-10-21T10:00:00Z",'
        '"branch":"main","changed_files":["src/payment.py"]}\n',
        encoding="utf-8",
    )

    (history_dir / "results.jsonl").write_text(
        '{"sha":"abc123","test_id":"tests/test_cart.py::test_add",'
        '"status":"failed","duration_s":1.0,"attempt":1}\n'
        '{"sha":"def456","test_id":"tests/test_payment.py::test_pay",'
        '"status":"passed","duration_s":2.0,"attempt":1}\n',
        encoding="utf-8",
    )

    rows = check_history(history_dir)

    summary = next(row for row in rows if row["category"] == "run_summary")

    assert summary["total"] == 2
    assert summary["failing_runs"] == 1
