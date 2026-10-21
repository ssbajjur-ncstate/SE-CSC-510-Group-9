import json

import pytest

from testbudget.links.report import format_report, read_links_file, summarize_links

LINKS = {
    "t1": [
        {"file": "a.py", "source": "import", "weight": 1.0},
        {"file": "b.py", "source": "pin", "weight": 10.0},
    ],
    "t2": [],
}


def test_summarize_counts():
    s = summarize_links(LINKS)
    assert s["tests"] == 2
    assert s["tests_with_links"] == 1
    assert s["tests_without_links"] == 1
    assert s["by_source"] == {"import": 1, "pin": 1}


def test_empty_links_summary():
    s = summarize_links({})
    assert s["tests"] == 0 and s["total_links"] == 0


def test_format_report_mentions_sources():
    text = format_report(summarize_links(LINKS))
    assert "import: 1" in text and "Total links: 2" in text


def test_format_report_empty_says_none():
    assert "(none)" in format_report(summarize_links({}))


def test_read_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_links_file(tmp_path / "nope.json")


def test_read_invalid_json_raises(tmp_path):
    p = tmp_path / "links.json"
    p.write_text("{not json")
    with pytest.raises(ValueError):
        read_links_file(p)


def test_read_valid_file(tmp_path):
    p = tmp_path / "links.json"
    p.write_text(json.dumps(LINKS))
    assert read_links_file(p) == LINKS


def test_summarize_handles_plain_string_entries():
    s = summarize_links({"t1": ["src/a.py", "src/b.py"]})
    assert s["total_links"] == 2
    assert s["by_source"] == {"unlabelled": 2}


def test_summarize_skips_non_list_values():
    s = summarize_links({"t1": "oops"})
    assert s["tests_with_links"] == 0


def test_read_non_object_json_raises(tmp_path):
    p = tmp_path / "links.json"
    p.write_text("[1, 2, 3]")
    with pytest.raises(ValueError):
        read_links_file(p)
