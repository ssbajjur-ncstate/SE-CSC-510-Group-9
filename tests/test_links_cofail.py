import pytest

from testbudget.links.cofail import build_cofail_links, read_jsonl

RUNS = [
    {"sha": "s1", "changed_files": ["a.py", "b.py"]},
    {"sha": "s2", "changed_files": ["a.py"]},
]


def test_weights_scaled_to_max():
    results = [
        {"sha": "s1", "test_id": "t", "status": "failed"},
        {"sha": "s2", "test_id": "t", "status": "failed"},
    ]
    links = build_cofail_links(RUNS, results)["t"]
    weights = {link["file"]: link["weight"] for link in links}
    assert weights == {"a.py": 1.0, "b.py": 0.5}


def test_no_failures_gives_empty():
    results = [{"sha": "s1", "test_id": "t", "status": "passed"}]
    assert build_cofail_links(RUNS, results) == {}


def test_retries_counted_once():
    results = [
        {"sha": "s1", "test_id": "t", "status": "failed", "attempt": 1},
        {"sha": "s1", "test_id": "t", "status": "failed", "attempt": 2},
    ]
    links = build_cofail_links(RUNS, results)["t"]
    weights = {link["file"]: link["weight"] for link in links}
    assert weights == {"a.py": 1.0, "b.py": 1.0}


def test_corrupt_jsonl_raises(tmp_path):
    p = tmp_path / "runs.jsonl"
    p.write_text('{"a": 1}\n{bad\n')
    with pytest.raises(ValueError):
        read_jsonl(p)
