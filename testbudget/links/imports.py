"""Static import links: which source files does a test import?"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def extract_imports(source: str) -> list[tuple[str, int]]:
    """Return (module, level) pairs for every import in ``source``.

    Returns an empty list if the source cannot be parsed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        log.warning("could not parse source, skipping")
        return []
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(alias.name, 0) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            found.append((node.module or "", node.level))
    return found


def resolve_module(module: str, level: int, importer: Path, root: Path) -> Path | None:
    """Map a module name to a file inside ``root``, or None if not in the repo."""
    base = importer.parent if level else root
    for _ in range(max(level - 1, 0)):
        base = base.parent
    parts = module.split(".") if module else []
    candidate = base.joinpath(*parts)
    for option in (candidate.with_suffix(".py"), candidate / "__init__.py"):
        if option.is_file():
            return option
    return None


def test_functions(source: str) -> list[str]:
    """Names of test functions in a test file (empty list if unparsable)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]


def build_import_links(root: Path, test_dir: str = "tests") -> dict[str, list[dict]]:
    """Build ``{test_id: [{file, source, weight}]}`` for every test file."""
    links: dict[str, list[dict]] = {}
    for test_file in sorted((root / test_dir).rglob("test_*.py")):
        source = test_file.read_text(encoding="utf-8", errors="ignore")
        files = []
        for module, level in extract_imports(source):
            target = resolve_module(module, level, test_file, root)
            if target is not None:
                files.append(target.relative_to(root).as_posix())
        rel = test_file.relative_to(root).as_posix()
        for name in test_functions(source):
            links[f"{rel}::{name}"] = [
                {"file": f, "source": "import", "weight": 1.0}
                for f in sorted(set(files))
            ]
    return links
