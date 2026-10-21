"""Route links: Playwright page.goto('/path') -> Next.js route file."""

from __future__ import annotations

import re
from pathlib import Path

PAGE_FILES = {"page.tsx", "page.jsx", "page.ts", "page.js"}
PAGE_EXTS = {".tsx", ".jsx", ".ts", ".js"}
GOTO_ANY = re.compile(r"page\.goto\(")
GOTO_LITERAL = re.compile(r"""page\.goto\(\s*(['"])(?P<path>[^'"`$]*)\1""")
TEST_TITLE = re.compile(r"""\btest\(\s*(['"])(?P<title>.+?)\1""")


def segments_to_regex(segments: list[str]) -> re.Pattern:
    """Turn route segments like ['users', '[id]'] into a URL-matching regex."""
    parts = []
    for seg in segments:
        if seg.startswith("[[..."):
            parts.append(r"(?:/.*)?")
        elif seg.startswith("[..."):
            parts.append(r"/.+")
        elif seg.startswith("["):
            parts.append(r"/[^/]+")
        else:
            parts.append("/" + re.escape(seg))
    return re.compile("^" + ("".join(parts) or "/") + "$")


def build_route_table(root: Path) -> list[tuple[re.Pattern, str]]:
    """Scan app/ (App Router) and pages/ (Pages Router); returns (regex, file) pairs."""
    table: list[tuple[re.Pattern, str]] = []
    for app in (root / "app", root / "src" / "app"):
        for p in app.rglob("page.*") if app.is_dir() else []:
            if p.name in PAGE_FILES:
                segs = [
                    s
                    for s in p.parent.relative_to(app).parts
                    if not (s.startswith("(") and s.endswith(")"))
                ]
                table.append((segments_to_regex(segs), p.relative_to(root).as_posix()))
    for pages in (root / "pages", root / "src" / "pages"):
        for p in pages.rglob("*") if pages.is_dir() else []:
            rel = p.relative_to(pages)
            if (
                p.suffix not in PAGE_EXTS
                or p.name.startswith("_")
                or rel.parts[0] == "api"
            ):
                continue
            segs = list(rel.with_suffix("").parts)
            if segs[-1] == "index":
                segs.pop()
            table.append((segments_to_regex(segs), p.relative_to(root).as_posix()))
    return table


def extract_goto_paths(source: str) -> tuple[list[str], int]:
    """Return (literal paths, total goto calls). Template strings count as unresolved."""
    paths = [m.group("path") for m in GOTO_LITERAL.finditer(source)]
    return paths, len(GOTO_ANY.findall(source))


def resolve_route(url_path: str, table: list[tuple[re.Pattern, str]]) -> str | None:
    """Match a URL path (query/hash/trailing slash ignored) to a route file."""
    clean = re.split(r"[?#]", url_path)[0]
    if len(clean) > 1:
        clean = clean.rstrip("/")
    for pattern, file in table:
        if pattern.match(clean):
            return file
    return None


def build_route_links(
    root: Path, spec_dir: str = "e2e"
) -> tuple[dict[str, list[dict]], dict]:
    """Return (links, stats). Every test in a spec links to every route that spec visits."""
    table = build_route_table(root)
    links: dict[str, list[dict]] = {}
    total = resolved = 0
    specs = (
        sorted((root / spec_dir).rglob("*.spec.*"))
        if (root / spec_dir).is_dir()
        else []
    )
    for spec in specs:
        source = spec.read_text(encoding="utf-8", errors="ignore")
        paths, calls = extract_goto_paths(source)
        total += calls
        files = set()
        for path in paths:
            hit = resolve_route(path, table)
            if hit:
                resolved += 1
                files.add(hit)
        rel = spec.relative_to(root).as_posix()
        for m in TEST_TITLE.finditer(source):
            links[f"{rel} › {m.group('title')}"] = [
                {"file": f, "source": "route", "weight": 1.0} for f in sorted(files)
            ]
    fraction = resolved / total if total else 0.0
    return links, {"goto_calls": total, "resolved": resolved, "fraction": fraction}
