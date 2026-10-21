import json

from testbudget.cli import main
from testbudget.db import get_all_results

FIXTURE = "fixtures/sample_junit.xml"


def test_init_creates_database(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"

    exit_code = main(
        [
            "init",
            "--db",
            str(db_path),
        ]
    )

    assert exit_code == 0
    assert db_path.exists()

    output = capsys.readouterr().out

    assert "Initialized TestBudget" in output
    assert str(db_path) in output


def test_ingest_stores_junit_results(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"

    exit_code = main(
        [
            "ingest",
            FIXTURE,
            "--db",
            str(db_path),
            "--changed-file",
            "src/checkout.py",
        ]
    )

    assert exit_code == 0

    stored = get_all_results(db_path)

    assert len(stored) == 5
    assert stored[0]["changed_file"] == "src/checkout.py"

    output = capsys.readouterr().out

    assert "Imported CI history" in output
    assert "Results: 5" in output
    assert "Failed: 2" in output


def test_ingest_rejects_missing_file(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"

    exit_code = main(
        [
            "ingest",
            "fixtures/does_not_exist.xml",
            "--db",
            str(db_path),
        ]
    )

    assert exit_code == 1

    output = capsys.readouterr().out

    assert "JUnit file not found" in output


def test_plan_prints_selected_and_skipped_tests(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"
    links_path = tmp_path / "test_links.json"

    links_path.write_text(
        json.dumps(
            {
                "src/checkout.py": [
                    "test_checkout_success",
                    "test_checkout_invalid_card",
                    "test_payment_timeout",
                ]
            }
        ),
        encoding="utf-8",
    )

    ingest_exit = main(
        [
            "ingest",
            FIXTURE,
            "--db",
            str(db_path),
            "--changed-file",
            "src/checkout.py",
        ]
    )

    assert ingest_exit == 0

    # Clear ingest output so we only inspect plan output.
    capsys.readouterr()

    plan_exit = main(
        [
            "plan",
            "--changed",
            "src/checkout.py",
            "--budget",
            "10",
            "--db",
            str(db_path),
            "--links",
            str(links_path),
        ]
    )

    assert plan_exit == 0

    output = capsys.readouterr().out

    assert "TESTBUDGET PLAN" in output
    assert "RANKED TESTS" in output
    assert "SELECTED" in output
    assert "SKIPPED" in output
    assert "Estimated runtime" in output
    assert "test_checkout_invalid_card" in output


def test_plan_rejects_empty_history(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"
    links_path = tmp_path / "test_links.json"

    links_path.write_text(
        json.dumps({"src/checkout.py": ["test_checkout"]}),
        encoding="utf-8",
    )

    # init creates an empty database with no test history.
    assert (
        main(
            [
                "init",
                "--db",
                str(db_path),
            ]
        )
        == 0
    )

    capsys.readouterr()

    exit_code = main(
        [
            "plan",
            "--changed",
            "src/checkout.py",
            "--budget",
            "10",
            "--db",
            str(db_path),
            "--links",
            str(links_path),
        ]
    )

    assert exit_code == 1

    output = capsys.readouterr().out
    assert "No test history found" in output


def test_plan_rejects_negative_budget(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"
    links_path = tmp_path / "test_links.json"

    links_path.write_text(
        json.dumps({"src/checkout.py": ["test_checkout"]}),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "plan",
            "--changed",
            "src/checkout.py",
            "--budget",
            "-1",
            "--db",
            str(db_path),
            "--links",
            str(links_path),
        ]
    )

    assert exit_code == 1

    output = capsys.readouterr().out
    assert "Budget cannot be negative" in output


def test_links_report_missing_file(tmp_path, capsys):
    from testbudget.cli import main

    code = main(["links", "--report", "--links", str(tmp_path / "nope.json")])

    assert code == 1
    assert "not found" in capsys.readouterr().out


def test_links_report_prints_summary(tmp_path, capsys):
    import json

    from testbudget.cli import main

    links_file = tmp_path / "links.json"
    links_file.write_text(
        json.dumps(
            {
                "tests/t.py::test_a": [
                    {"file": "src/a.py", "source": "import", "weight": 1.0}
                ]
            }
        )
    )

    code = main(["links", "--report", "--links", str(links_file)])

    assert code == 0
    assert "import: 1" in capsys.readouterr().out


def test_links_without_report_flag_does_nothing(capsys):
    from testbudget.cli import main

    assert main(["links"]) == 1
    assert "Use --report" in capsys.readouterr().out


def test_plan_writes_plan_json_with_forced_pin_on_fixtures(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"
    config_path = tmp_path / "testbudget.yml"
    output_path = tmp_path / "plan.json"
    config_path.write_text("pins:\n  - test_login_success\n", encoding="utf-8")
    assert main(["ingest", FIXTURE, "--db", str(db_path)]) == 0

    exit_code = main(
        [
            "plan",
            "--changed",
            "src/checkout.py",
            "--budget",
            "0",
            "--db",
            str(db_path),
            "--links",
            "fixtures/test_links.json",
            "--config",
            str(config_path),
            "--history",
            "fixtures/history_small",
            "--sha",
            "abc123",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    plan = json.loads(output_path.read_text(encoding="utf-8"))
    assert plan["sha"] == "abc123"
    assert plan["risk_level"] in {"low", "medium", "high"}
    assert [t["test_id"] for t in plan["selected"]] == ["test_login_success"]
    assert all({"skip_reason", "skip_debt"} <= set(t) for t in plan["skipped"])


def test_plan_rejects_malformed_config(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"
    config_path = tmp_path / "testbudget.yml"
    config_path.write_text("pins: 3\n", encoding="utf-8")
    assert main(["ingest", FIXTURE, "--db", str(db_path)]) == 0

    exit_code = main(
        [
            "plan",
            "--changed",
            "src/checkout.py",
            "--budget",
            "5",
            "--db",
            str(db_path),
            "--links",
            "fixtures/test_links.json",
            "--config",
            str(config_path),
        ]
    )

    assert exit_code == 1
    assert "pins must be" in capsys.readouterr().out


def test_links_build_writes_every_source_on_fixtures(tmp_path, capsys):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "pay.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_pay.py").write_text(
        "from src.pay import X\n\n\ndef test_charge():\n    assert X\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "testbudget.yml"
    config_path.write_text(
        "pins:\n  tests/test_pay.py::test_charge: [src/pay.py]\n", encoding="utf-8"
    )
    output_path = tmp_path / "links.json"

    exit_code = main(
        [
            "links",
            "--build",
            "--report",
            "--root",
            str(tmp_path),
            "--history",
            "fixtures/history_small",
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    links = json.loads(output_path.read_text(encoding="utf-8"))
    sources = {entry["source"] for entry in links["tests/test_pay.py::test_charge"]}
    assert {"import", "cofail", "pin"} <= sources
    assert "Links written" in capsys.readouterr().out


def test_links_build_rejects_malformed_config(tmp_path, capsys):
    config_path = tmp_path / "testbudget.yml"
    config_path.write_text("pins: [a, b]\n", encoding="utf-8")

    exit_code = main(
        [
            "links",
            "--build",
            "--root",
            str(tmp_path),
            "--history",
            str(tmp_path / "missing"),
            "--config",
            str(config_path),
            "--output",
            str(tmp_path / "links.json"),
        ]
    )

    assert exit_code == 1
    assert "pins must map" in capsys.readouterr().out


def test_calibrate_writes_budgets_from_replay_fixture(tmp_path, capsys):
    output_path = tmp_path / "testbudget.yml"
    output_path.write_text("pins: []\n", encoding="utf-8")

    exit_code = main(
        [
            "calibrate",
            "--replay",
            "fixtures/replay_synthetic.csv",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    text = output_path.read_text(encoding="utf-8")
    assert text.startswith("pins: []\n")
    for level in ("low", "medium", "high"):
        assert f"  {level}:" in text
    assert "Calibrated budgets" in capsys.readouterr().out


def test_calibrate_rejects_missing_replay_file(tmp_path, capsys):
    exit_code = main(
        [
            "calibrate",
            "--replay",
            str(tmp_path / "missing.csv"),
            "--output",
            str(tmp_path / "testbudget.yml"),
        ]
    )

    assert exit_code == 1
    assert not (tmp_path / "testbudget.yml").exists()


def test_calibrate_rejects_floor_above_ceiling(tmp_path, capsys):
    exit_code = main(
        [
            "calibrate",
            "--replay",
            "fixtures/replay_synthetic.csv",
            "--floor",
            "0.9",
            "--ceiling",
            "0.5",
            "--output",
            str(tmp_path / "testbudget.yml"),
        ]
    )

    assert exit_code == 1
    assert "floor and ceiling" in capsys.readouterr().out


def _plan_args(db_path, *extra):
    return [
        "plan",
        "--changed",
        "src/checkout.py",
        "--budget",
        "2",
        "--db",
        str(db_path),
        "--links",
        "fixtures/test_links.json",
        "--history",
        "fixtures/history_small",
        *extra,
    ]


def test_plan_audit_runs_every_test_but_keeps_the_plan(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"
    policy_path = tmp_path / "policy.json"
    plan_path = tmp_path / "plan.json"
    assert main(["ingest", FIXTURE, "--db", str(db_path)]) == 0

    exit_code = main(
        _plan_args(
            db_path,
            "--audit",
            "--output",
            str(plan_path),
            "--policy-output",
            str(policy_path),
        )
    )

    assert exit_code == 0
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert policy["mode"] == "audit"
    assert len(policy["execute_test_ids"]) == 5
    assert len(plan["selected"]) < 5
    assert "Execution mode: audit" in capsys.readouterr().out


def test_plan_reviewer_full_override_runs_every_test(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"
    policy_path = tmp_path / "policy.json"
    assert main(["ingest", FIXTURE, "--db", str(db_path)]) == 0

    exit_code = main(
        _plan_args(
            db_path,
            "--reviewer-comment",
            "/testbudget full",
            "--reviewer-permission",
            "write",
            "--policy-output",
            str(policy_path),
        )
    )

    assert exit_code == 0
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    assert policy["mode"] == "reviewer_full"


def test_plan_rejects_unauthorized_reviewer_override(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"
    assert main(["ingest", FIXTURE, "--db", str(db_path)]) == 0

    exit_code = main(_plan_args(db_path, "--reviewer-comment", "/testbudget full"))

    assert exit_code == 1


def test_migrate_moves_ingested_history_into_jsonl(tmp_path, capsys):
    from testbudget.db import load_history_records

    db_path = tmp_path / "legacy.db"
    history_dir = tmp_path / "history"
    assert main(["ingest", FIXTURE, "--db", str(db_path)]) == 0

    exit_code = main(
        ["migrate", "--db", str(db_path), "--history-dir", str(history_dir)]
    )

    assert exit_code == 0
    runs, results = load_history_records(history_dir)
    assert len(runs) == 1
    assert len(results) == 5


def test_migrate_rejects_missing_database(tmp_path, capsys):
    exit_code = main(
        [
            "migrate",
            "--db",
            str(tmp_path / "missing.db"),
            "--history-dir",
            str(tmp_path / "history"),
        ]
    )

    assert exit_code == 1
    assert "Migration failed" in capsys.readouterr().err
