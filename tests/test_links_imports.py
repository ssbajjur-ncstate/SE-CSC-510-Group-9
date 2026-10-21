from pathlib import Path

from testbudget.links.imports import build_import_links, extract_imports


def test_extract_imports_basic():
    assert ("os", 0) in extract_imports("import os\n")


def test_unparsable_source_returns_empty():
    assert extract_imports("def broken(:\n") == []


def test_build_links_finds_source_file(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "checkout.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text(
        "import src.checkout\ndef test_pay():\n    pass\n")
    links = build_import_links(tmp_path)
    assert links["tests/test_a.py::test_pay"][0]["file"] == "src/checkout.py"


def test_no_test_dir_gives_empty(tmp_path: Path):
    assert build_import_links(tmp_path) == {}
