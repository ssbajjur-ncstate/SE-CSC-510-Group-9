import pytest

from testbudget.calibrate import read_replay_csv

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
