import pytest

from testbudget.links.pins import build_pin_links


def test_pin_links(tmp_path):
    cfg = tmp_path / "testbudget.yml"
    cfg.write_text('pins:\n  "tests/t.py::test_a": ["src/a.py"]\n')
    links = build_pin_links(cfg)
    assert links["tests/t.py::test_a"][0]["source"] == "pin"


def test_no_pins_key_gives_empty(tmp_path):
    cfg = tmp_path / "testbudget.yml"
    cfg.write_text("target: 0.85\n")
    assert build_pin_links(cfg) == {}


def test_unknown_test_raises(tmp_path):
    cfg = tmp_path / "testbudget.yml"
    cfg.write_text('pins:\n  "tests/t.py::nope": ["src/a.py"]\n')
    with pytest.raises(ValueError):
        build_pin_links(cfg, known_tests={"tests/t.py::test_a"})


def test_malformed_yml_raises(tmp_path):
    cfg = tmp_path / "testbudget.yml"
    cfg.write_text("pins: [unclosed")
    with pytest.raises(ValueError):
        build_pin_links(cfg)
