"""Pinned links from testbudget.yml."""

from __future__ import annotations

from pathlib import Path

import yaml

PIN_WEIGHT = 10.0


def build_pin_links(
    config_path: str | Path,
    known_tests: set[str] | None = None,
) -> dict[str, list[dict]]:
    """Return pin links; raises ValueError for malformed yml or unknown test IDs."""
    try:
        config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed {config_path}") from exc
    pins = config.get("pins") or {}
    if not isinstance(pins, dict):
        raise ValueError("pins must map test_id -> list of files")
    links = {}
    for test_id, files in pins.items():
        if known_tests is not None and test_id not in known_tests:
            raise ValueError(f"pin refers to unknown test: {test_id}")
        links[test_id] = [
            {"file": f, "source": "pin", "weight": PIN_WEIGHT} for f in files
        ]
    return links
