import pytest

from testbudget.calibrate import (
    BLOCK_END,
    BLOCK_START,
    CalibrationParams,
    calibrate,
    catch_rates,
    format_calibration,
    read_replay_csv,
    write_calibration,
)

FIXTURE = "fixtures/replay_synthetic.csv"
HEADER = "sha,risk_level,budget_fraction,caught\n"


def write_csv(tmp_path, text, name="replay.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_synthetic_fixture_is_read_in_full():
    rows = read_replay_csv(FIXTURE)
    assert len(rows) == 600
    assert rows[0] == {
        "sha": "l000",
        "risk_level": "low",
        "budget_fraction": 0.1,
        "caught": 1,
    }


def test_extra_columns_and_blank_lines_are_ignored(tmp_path):
    path = write_csv(
        tmp_path,
        "risk_level,sha,caught,budget_fraction,method\nhigh,abc,0,0.25,testbudget\n\n",
    )
    assert read_replay_csv(path) == [
        {"sha": "abc", "risk_level": "high", "budget_fraction": 0.25, "caught": 0}
    ]


def test_missing_file_fails_with_its_path(tmp_path):
    with pytest.raises(FileNotFoundError, match="replay CSV not found"):
        read_replay_csv(tmp_path / "nope.csv")


def test_empty_file_fails_with_a_clear_message(tmp_path):
    with pytest.raises(ValueError, match="replay CSV is empty"):
        read_replay_csv(write_csv(tmp_path, ""))


def test_header_without_rows_fails_with_a_clear_message(tmp_path):
    with pytest.raises(ValueError, match="header but no rows"):
        read_replay_csv(write_csv(tmp_path, HEADER))


def test_missing_column_is_named(tmp_path):
    path = write_csv(tmp_path, "sha,risk_level,caught\nabc,low,1\n")
    with pytest.raises(ValueError, match="missing columns: budget_fraction"):
        read_replay_csv(path)


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (",low,0.5,1", "sha is empty"),
        ("abc,critical,0.5,1", "risk_level must be one of"),
        ("abc,low,half,1", "not a number"),
        ("abc,low,0,1", r"must be in \(0, 1\]"),
        ("abc,low,1.5,1", r"must be in \(0, 1\]"),
        ("abc,low,nan,1", r"must be in \(0, 1\]"),
        ("abc,low,0.5,yes", "caught must be 0 or 1"),
    ],
)
def test_malformed_row_fails_naming_the_line(tmp_path, row, message):
    path = write_csv(tmp_path, HEADER + "ok,low,0.5,1\n" + row + "\n")
    with pytest.raises(ValueError, match=message) as error:
        read_replay_csv(path)
    assert "replay.csv:3" in str(error.value)


def rows_for(level, detects, fractions=(0.1, 0.2, 0.3, 0.4, 0.5)):
    """Build replay rows where run i is caught at fractions >= detects[i]."""
    return [
        {
            "sha": f"{level}{index}",
            "risk_level": level,
            "budget_fraction": fraction,
            "caught": int(fraction >= detect),
        }
        for index, detect in enumerate(detects)
        for fraction in fractions
    ]


def test_calibration_recovers_the_planted_budgets():
    budgets = calibrate(read_replay_csv(FIXTURE))
    assert {level: b["budget_fraction"] for level, b in budgets.items()} == {
        "low": 0.2,
        "medium": 0.4,
        "high": 0.5,
    }
    assert all(b["calibrated"] for b in budgets.values())
    assert budgets["low"]["catch_rate"] == pytest.approx(0.95)
    assert budgets["high"]["failing_runs"] == 20


def test_catch_rate_is_the_share_caught_at_each_fraction():
    rows = rows_for("low", [0.1, 0.3, 0.5, 0.5])
    assert catch_rates(rows, "low") == {
        0.1: 0.25,
        0.2: 0.25,
        0.3: 0.5,
        0.4: 0.5,
        0.5: 1.0,
    }
    assert catch_rates(rows, "high") == {}


def test_sparse_level_inherits_the_next_higher_budget():
    rows = (
        rows_for("high", [0.3] * 12)
        + rows_for("medium", [0.1] * 3)
        + rows_for("low", [0.1] * 2)
    )
    budgets = calibrate(rows, CalibrationParams(floor=0.0, min_failing_runs=10))
    assert budgets["high"] == {
        "budget_fraction": 0.3,
        "calibrated": True,
        "catch_rate": 1.0,
        "failing_runs": 12,
        "note": "met target at 0.3 (catch rate 1.000)",
    }
    assert budgets["medium"]["budget_fraction"] == 0.3
    assert budgets["medium"]["calibrated"] is False
    assert budgets["medium"]["note"] == "3 of 10 failing runs; inherited from high"
    assert budgets["low"]["budget_fraction"] == 0.3
    assert budgets["low"]["note"] == "2 of 10 failing runs; inherited from medium"


def test_sparse_high_level_falls_back_to_the_ceiling():
    rows = rows_for("low", [0.1] * 12)
    budgets = calibrate(rows, CalibrationParams(ceiling=0.7))
    assert budgets["high"]["budget_fraction"] == 0.7
    assert budgets["high"]["calibrated"] is False
    assert budgets["high"]["failing_runs"] == 0
    assert budgets["medium"]["budget_fraction"] == 0.7
    assert budgets["low"]["calibrated"] is True


def test_budget_below_the_floor_is_raised_to_the_floor():
    rows = rows_for("high", [0.1] * 10)
    budgets = calibrate(rows, CalibrationParams(floor=0.25, min_failing_runs=5))
    assert budgets["high"]["budget_fraction"] == 0.25
    assert budgets["high"]["note"] == "met target at 0.1; raised to floor"


def test_budget_above_the_ceiling_is_capped_at_the_ceiling():
    rows = rows_for("high", [0.5] * 10)
    budgets = calibrate(rows, CalibrationParams(ceiling=0.4, min_failing_runs=5))
    assert budgets["high"]["budget_fraction"] == 0.4
    assert budgets["high"]["note"] == "met target at 0.5; capped at ceiling"


def test_unmet_target_uses_the_ceiling():
    rows = rows_for("high", [0.1] * 5 + [0.9] * 5)
    budgets = calibrate(rows, CalibrationParams(min_failing_runs=5))
    assert budgets["high"]["budget_fraction"] == 0.6
    assert budgets["high"]["catch_rate"] == 0.5
    assert budgets["high"]["note"] == "target not met at any fraction; using ceiling"


def test_calibration_of_an_empty_replay_fails():
    with pytest.raises(ValueError, match="empty replay"):
        calibrate([])


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"target_catch_rate": 0.0}, "target_catch_rate"),
        ({"target_catch_rate": 1.5}, "target_catch_rate"),
        ({"floor": 0.5, "ceiling": 0.4}, "floor and ceiling"),
        ({"ceiling": 1.2}, "floor and ceiling"),
        ({"floor": -0.1}, "floor and ceiling"),
        ({"min_failing_runs": 0}, "min_failing_runs"),
    ],
)
def test_bad_calibration_settings_are_rejected(settings, message):
    with pytest.raises(ValueError, match=message):
        CalibrationParams(**settings)


PARAMS = CalibrationParams()
BUDGETS = calibrate(read_replay_csv(FIXTURE), PARAMS)

EXPECTED_BLOCK = f"""{BLOCK_START}
calibrated_with:
  target_catch_rate: 0.9
  floor: 0.1
  ceiling: 0.6
  min_failing_runs: 10
budgets:
  low:
    budget_fraction: 0.2
    calibrated: true
    catch_rate: 0.95
    failing_runs: 20
    note: "met target at 0.2 (catch rate 0.950)"
  medium:
    budget_fraction: 0.4
    calibrated: true
    catch_rate: 0.95
    failing_runs: 20
    note: "met target at 0.4 (catch rate 0.950)"
  high:
    budget_fraction: 0.5
    calibrated: true
    catch_rate: 0.95
    failing_runs: 20
    note: "met target at 0.5 (catch rate 0.950)"
{BLOCK_END}
"""


def test_calibration_block_has_a_fixed_layout():
    assert format_calibration(BUDGETS, PARAMS) == EXPECTED_BLOCK


def test_uncalibrated_level_is_written_with_a_null_catch_rate():
    budgets = calibrate(rows_for("high", [0.3] * 12), PARAMS)
    block = format_calibration(budgets, PARAMS)
    assert "    calibrated: false\n    catch_rate: null\n    failing_runs: 0\n" in block


def test_missing_config_is_created_with_the_block(tmp_path):
    path = tmp_path / "testbudget.yml"
    write_calibration(path, BUDGETS, PARAMS)
    assert path.read_text(encoding="utf-8") == EXPECTED_BLOCK


def test_hand_written_config_is_kept_and_the_block_appended(tmp_path):
    path = tmp_path / "testbudget.yml"
    path.write_text("# team config\npins:\n  - tests/test_a.py::test_one", "utf-8")
    write_calibration(path, BUDGETS, PARAMS)
    assert path.read_text(encoding="utf-8") == (
        "# team config\npins:\n  - tests/test_a.py::test_one\n\n" + EXPECTED_BLOCK
    )


def test_rerun_replaces_the_block_in_place(tmp_path):
    path = tmp_path / "testbudget.yml"
    path.write_text("pins: []\n", encoding="utf-8")
    write_calibration(path, calibrate(rows_for("high", [0.3] * 12), PARAMS), PARAMS)
    path.write_text(path.read_text(encoding="utf-8") + "rotation_limit: 10\n", "utf-8")
    write_calibration(path, BUDGETS, PARAMS)
    assert path.read_text(encoding="utf-8") == (
        "pins: []\n\n" + EXPECTED_BLOCK + "rotation_limit: 10\n"
    )


def test_rerun_with_the_same_input_gives_identical_bytes(tmp_path):
    path = tmp_path / "testbudget.yml"
    write_calibration(path, BUDGETS, PARAMS)
    first = path.read_bytes()
    write_calibration(path, BUDGETS, PARAMS)
    assert path.read_bytes() == first


def test_written_config_parses_as_yaml(tmp_path):
    yaml = pytest.importorskip("yaml")
    path = tmp_path / "testbudget.yml"
    path.write_text("pins:\n  - tests/test_a.py::test_one\n", encoding="utf-8")
    write_calibration(path, BUDGETS, PARAMS)
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert config["pins"] == ["tests/test_a.py::test_one"]
    assert config["budgets"]["medium"]["budget_fraction"] == 0.4
    assert config["calibrated_with"]["min_failing_runs"] == 10


@pytest.mark.parametrize("text", [BLOCK_START + "\n", BLOCK_END + "\n"])
def test_config_with_a_broken_block_is_rejected(tmp_path, text):
    path = tmp_path / "testbudget.yml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="one generated calibration block"):
        write_calibration(path, BUDGETS, PARAMS)


def test_hand_written_budgets_key_is_rejected(tmp_path):
    path = tmp_path / "testbudget.yml"
    path.write_text("budgets:\n  low: 0.3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="'budgets' is set outside"):
        write_calibration(path, BUDGETS, PARAMS)
    assert path.read_text(encoding="utf-8") == "budgets:\n  low: 0.3\n"
