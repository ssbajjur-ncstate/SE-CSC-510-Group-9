import json

import pytest

from testbudget.links.writer import merge_links, validate_links, write_links

GOOD = {"tests/test_a.py::test_x": [{"file": "src/a.py", "source": "import", "weight": 1.0}]}


def test_write_links_round_trip(tmp_path):
    out = tmp_path / "links.json"
    write_links(GOOD, out)
    assert json.loads(out.read_text()) == GOOD


def test_empty_links_writes_empty_object(tmp_path):
    out = tmp_path / "links.json"
    write_links({}, out)
    assert json.loads(out.read_text()) == {}


def test_bad_source_raises():
    with pytest.raises(ValueError):
        validate_links({"t": [{"file": "a.py", "source": "magic", "weight": 1.0}]})


def test_negative_weight_raises():
    with pytest.raises(ValueError):
        validate_links({"t": [{"file": "a.py", "source": "import", "weight": -1}]})


def test_missing_file_raises():
    with pytest.raises(ValueError):
        validate_links({"t": [{"source": "import", "weight": 1.0}]})


def test_merge_concatenates():
    a = {"t": [{"file": "a.py", "source": "import", "weight": 1.0}]}
    b = {"t": [{"file": "b.py", "source": "pin", "weight": 10.0}]}
    assert len(merge_links(a, b)["t"]) == 2
