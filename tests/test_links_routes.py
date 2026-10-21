from pathlib import Path

from testbudget.links.routes import (
    build_route_links,
    build_route_table,
    extract_goto_paths,
    resolve_route,
)


def make_app(root: Path):
    for rel in [
        "app/users/[id]/page.tsx",
        "app/(marketing)/about/page.tsx",
        "pages/index.tsx",
    ]:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("export default function P(){}\n")


def test_dynamic_segment_resolves(tmp_path):
    make_app(tmp_path)
    table = build_route_table(tmp_path)
    assert resolve_route("/users/42", table) == "app/users/[id]/page.tsx"


def test_route_group_ignored(tmp_path):
    make_app(tmp_path)
    assert (
        resolve_route("/about", build_route_table(tmp_path))
        == "app/(marketing)/about/page.tsx"
    )


def test_pages_router_index(tmp_path):
    make_app(tmp_path)
    assert resolve_route("/", build_route_table(tmp_path)) == "pages/index.tsx"


def test_no_matching_route_returns_none(tmp_path):
    make_app(tmp_path)
    assert resolve_route("/nope", build_route_table(tmp_path)) is None


def test_no_app_or_pages_dir_gives_empty_table(tmp_path):
    assert build_route_table(tmp_path) == []


def test_template_string_goto_is_unresolved():
    src = "await page.goto('/about');\nawait page.goto(`/users/${id}`);\n"
    paths, calls = extract_goto_paths(src)
    assert paths == ["/about"] and calls == 2


def test_zero_goto_calls_fraction_zero(tmp_path):
    make_app(tmp_path)
    (tmp_path / "e2e").mkdir()
    (tmp_path / "e2e" / "a.spec.ts").write_text("test('x', async () => {});\n")
    _, stats = build_route_links(tmp_path)
    assert stats["fraction"] == 0.0


def test_build_route_links_end_to_end(tmp_path):
    make_app(tmp_path)
    (tmp_path / "e2e").mkdir()
    (tmp_path / "e2e" / "a.spec.ts").write_text(
        "test('visits about', async ({page}) => { await page.goto('/about'); });\n"
    )
    links, stats = build_route_links(tmp_path)
    assert (
        links["e2e/a.spec.ts › visits about"][0]["file"]
        == "app/(marketing)/about/page.tsx"
    )
    assert stats["fraction"] == 1.0
