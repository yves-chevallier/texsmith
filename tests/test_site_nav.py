"""The navigation resolver against MkDocs' own answer and over temporary trees."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from texsmith.site.nav import (
    Navigation,
    NavLink,
    NavPage,
    NavSection,
    page_title,
    resolve_navigation,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"
REFERENCE_ORDER = Path(__file__).parent / "fixtures" / "site_nav" / "texsmith-docs-order.txt"
DOCS_EXCLUDE = "assets/**/*.md\n"


def write_tree(root: Path, tree: dict[str, str]) -> Path:
    """Write ``{relative path: contents}`` under ``root`` and return it."""
    for name, contents in tree.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    return root


def flat(navigation: Navigation) -> list[str]:
    return [page.src_uri for page in navigation.pages()]


def titles(items: tuple[Any, ...]) -> list[str | None]:
    return [item.title for item in items]


def test_resolves_the_texsmith_docs_exactly_like_mkdocs():
    """The page order must equal the one a real MkDocs build produces.

    Regenerate the fixture after changing ``docs/``, ``mkdocs.yml`` or the
    navigation of the site, with MkDocs installed::

        uv run python - <<'EOF'
        from pathlib import Path
        from mkdocs.config import load_config
        from mkdocs.structure.files import get_files
        from mkdocs.structure.nav import get_navigation

        config = load_config("mkdocs.yml")
        config.plugins.on_startup(command="build", dirty=False)
        files = config.plugins.on_files(get_files(config), config=config)
        nav = config.plugins.on_nav(get_navigation(files, config), config=config, files=files)
        Path("tests/fixtures/site_nav/texsmith-docs-order.txt").write_text(
            "".join(f"{page.file.src_uri}\n" for page in nav.pages)
        )
        EOF
    """
    navigation = resolve_navigation(DOCS_DIR, nav=None, exclude_docs=DOCS_EXCLUDE)
    expected = REFERENCE_ORDER.read_text(encoding="utf-8").split()
    assert flat(navigation) == expected


def test_texsmith_docs_section_titles_match_the_built_site():
    navigation = resolve_navigation(DOCS_DIR, nav=None, exclude_docs=DOCS_EXCLUDE)
    assert titles(navigation.items) == [
        "Home",
        "Guide",
        "Syntax",
        "Examples",
        "CLI",
        "API",
        "About",
    ]

    guide = next(item for item in navigation.items if item.title == "Guide")
    assert guide.index is None
    assert titles(guide.children) == [
        None,
        "Migrating to TMark",
        None,
        None,
        None,
        None,
        "Fragments",
        "Features",
        "Templates",
        "Plumbing",
        "MkDocs Integration",
        None,
        None,
        None,
        None,
    ]
    plumbing = next(item for item in guide.children if item.title == "Plumbing")
    assert plumbing.index is not None
    assert plumbing.index.src_uri == "guide/plumbing/index.md"


def test_texsmith_docs_leave_one_page_out_of_the_navigation():
    navigation = resolve_navigation(DOCS_DIR, nav=None, exclude_docs=DOCS_EXCLUDE)
    assert [page.src_uri for page in navigation.unlisted()] == ["guide/plumbing/arguments.md"]
    assert all(page.abs_path.is_file() for page in navigation.unlisted())


def test_default_navigation_nests_directories_with_the_index_first(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            "zebra.md": "",
            "index.md": "",
            "guide/beta.md": "",
            "guide/index.md": "",
            "guide/deep/alpha.md": "",
            "assets/style.css": "",
            ".hidden/secret.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == [
        "index.md",
        "zebra.md",
        "guide/index.md",
        "guide/beta.md",
        "guide/deep/alpha.md",
    ]
    assert titles(navigation.items) == [None, None, "Guide"]
    assert navigation.unlisted() == ()


def test_default_navigation_promotes_the_index_page_of_a_section(tmp_path: Path):
    write_tree(tmp_path, {"guide/index.md": "", "guide/beta.md": ""})
    navigation = resolve_navigation(tmp_path)
    section = navigation.items[0]
    assert isinstance(section, NavSection)
    assert section.index == NavPage(None, "guide/index.md", tmp_path / "guide/index.md")
    assert [child.src_uri for child in section.children] == ["guide/beta.md"]


def test_a_readme_gives_way_to_an_index_in_the_same_directory(tmp_path: Path):
    write_tree(tmp_path, {"README.md": "", "index.md": "", "sub/README.md": ""})
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == ["index.md", "sub/README.md"]


def test_a_plain_mkdocs_nav_orders_pages_sections_and_links(tmp_path: Path):
    write_tree(tmp_path, {"index.md": "", "guide/one.md": "", "guide/two.md": "", "lost.md": ""})
    navigation = resolve_navigation(
        tmp_path,
        nav=[
            "index.md",
            {"Guide": [{"First": "guide/two.md"}, "guide/one.md"]},
            {"Upstream": "https://example.org"},
        ],
    )
    assert flat(navigation) == ["index.md", "guide/two.md", "guide/one.md"]
    section = navigation.items[1]
    assert isinstance(section, NavSection)
    assert titles(section.children) == ["First", None]
    assert navigation.items[2] == NavLink("Upstream", "https://example.org")
    assert [page.src_uri for page in navigation.unlisted()] == ["lost.md"]


def test_exclude_docs_keeps_pages_out_of_the_navigation(tmp_path: Path):
    write_tree(
        tmp_path,
        {"index.md": "", "assets/embed.md": "", "assets/deep/embed.md": "", "draft.md": ""},
    )
    navigation = resolve_navigation(tmp_path, exclude_docs="assets/**/*.md\ndraft.md\n")
    assert flat(navigation) == ["index.md"]
    assert navigation.unlisted() == ()


def test_exclude_docs_understands_negated_patterns(tmp_path: Path):
    write_tree(tmp_path, {"index.md": "", "notes/a.md": "", "notes/keep.md": ""})
    navigation = resolve_navigation(tmp_path, exclude_docs="notes/*\n!notes/keep.md\n")
    assert flat(navigation) == ["index.md", "notes/keep.md"]


def test_a_nav_file_orders_pages_and_titles_them(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": "nav:\n  - Home: index.md\n  - second.md\n  - first.md\n",
            "index.md": "",
            "first.md": "",
            "second.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == ["index.md", "second.md", "first.md"]
    assert titles(navigation.items) == ["Home", None, None]


def test_a_nav_file_turns_directories_into_sections(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": "nav:\n  - Manual: guide/\n  - reference/\n",
            "guide/index.md": "",
            "guide/usage.md": "",
            "reference/api.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    assert titles(navigation.items) == ["Manual", "Reference"]
    assert flat(navigation) == ["guide/index.md", "guide/usage.md", "reference/api.md"]


def test_a_nav_file_takes_the_section_title_from_its_own_configuration(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            "guide/.nav.yml": "title: The Manual\n",
            "guide/index.md": "",
            "index.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    assert titles(navigation.items) == [None, "The Manual"]


def test_a_nav_file_accepts_globs_and_a_catch_all(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": 'nav:\n  - index.md\n  - "guide/*"\n  - "*"\n',
            "index.md": "",
            "guide/a.md": "",
            "guide/b.md": "",
            "later.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == ["index.md", "guide/a.md", "guide/b.md", "later.md"]
    assert isinstance(navigation.items[3], NavPage)


def test_a_globstar_claims_every_page_below_a_directory(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": 'nav:\n  - "**"\n',
            "index.md": "",
            "guide/deep/a.md": "",
            "guide/b.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    # An explicit nav replaces the implicit "index first, then the rest", so the
    # globstar's own path order rules: every page, directories left empty behind.
    assert flat(navigation) == ["guide/b.md", "guide/deep/a.md", "index.md"]


def test_a_nav_file_nests_inline_sections_and_links(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": (
                "nav:\n"
                "  - Group:\n"
                "      - a.md\n"
                "      - Nested:\n"
                "          - b.md\n"
                "  - Upstream: https://example.org\n"
            ),
            "a.md": "",
            "b.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    group = navigation.items[0]
    assert isinstance(group, NavSection)
    assert group.title == "Group"
    nested = group.children[1]
    assert isinstance(nested, NavSection)
    assert titles(nested.children) == [None]
    assert navigation.items[1] == NavLink("Upstream", "https://example.org")
    assert flat(navigation) == ["a.md", "b.md"]


def test_an_index_page_becomes_the_section_index(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            "guide/.nav.yml": "nav:\n  - index.md\n  - usage.md\n",
            "guide/index.md": "",
            "guide/usage.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    section = navigation.items[0]
    assert isinstance(section, NavSection)
    assert section.index is not None
    assert section.index.src_uri == "guide/index.md"
    assert [child.src_uri for child in section.children] == ["guide/usage.md"]
    assert flat(navigation) == ["guide/index.md", "guide/usage.md"]


def test_ignore_hides_pages_from_the_patterns_of_a_directory(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": "ignore:\n  - draft.md\n",
            "index.md": "",
            "draft.md": "",
            "guide/draft.md": "",
            "guide/real.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == ["index.md", "guide/real.md"]
    assert [page.src_uri for page in navigation.unlisted()] == ["draft.md", "guide/draft.md"]


def test_an_anchored_ignore_pattern_only_applies_to_its_own_directory(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": "ignore: /draft.md\n",
            "index.md": "",
            "draft.md": "",
            "guide/draft.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == ["index.md", "guide/draft.md"]


def test_sort_can_be_alphabetical_and_reversed(tmp_path: Path):
    write_tree(tmp_path, {".nav.yml": "\n", "ch2.md": "", "ch10.md": "", "index.md": ""})
    natural = resolve_navigation(tmp_path)
    assert flat(natural) == ["index.md", "ch2.md", "ch10.md"]

    write_tree(tmp_path, {".nav.yml": "sort:\n  type: alphabetical\n"})
    alphabetical = resolve_navigation(tmp_path)
    assert flat(alphabetical) == ["index.md", "ch10.md", "ch2.md"]

    write_tree(tmp_path, {".nav.yml": "sort:\n  direction: desc\n"})
    descending = resolve_navigation(tmp_path)
    assert flat(descending) == ["index.md", "ch10.md", "ch2.md"]


def test_sort_can_ignore_case_and_use_titles(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": "sort:\n  by: title\n  ignore_case: true\n",
            "one.md": "---\ntitle: zulu\n---\n",
            "two.md": "---\ntitle: Alpha\n---\n",
        },
    )
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == ["two.md", "one.md"]


def test_sort_places_sections_first_or_last(tmp_path: Path):
    write_tree(tmp_path, {".nav.yml": "\n", "zzz/a.md": "", "page.md": ""})
    assert flat(resolve_navigation(tmp_path)) == ["page.md", "zzz/a.md"]

    write_tree(tmp_path, {".nav.yml": "sort:\n  sections: first\n"})
    assert flat(resolve_navigation(tmp_path)) == ["zzz/a.md", "page.md"]


def test_a_pattern_carries_its_own_sort_options(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": 'nav:\n  - glob: "*.md"\n    sort:\n      direction: desc\n',
            "a.md": "",
            "b.md": "",
            "c.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == ["c.md", "b.md", "a.md"]


def test_preserve_directory_names_keeps_the_directory_spelling(tmp_path: Path):
    write_tree(
        tmp_path,
        {".nav.yml": "preserve_directory_names: true\n", "my-guide/a.md": ""},
    )
    assert titles(resolve_navigation(tmp_path).items) == ["my-guide"]

    write_tree(tmp_path, {".nav.yml": "\n"})
    assert titles(resolve_navigation(tmp_path).items) == ["My guide"]


def test_use_index_title_names_a_section_after_its_index_page(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": "use_index_title: true\n",
            "guide/index.md": "---\ntitle: The Manual\n---\n",
            "guide/a.md": "",
        },
    )
    assert titles(resolve_navigation(tmp_path).items) == ["The Manual"]


def test_flatten_single_child_sections_drops_the_lonely_section(tmp_path: Path):
    write_tree(
        tmp_path,
        {".nav.yml": "flatten_single_child_sections: true\n", "solo/only.md": "", "index.md": ""},
    )
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == ["index.md", "solo/only.md"]
    assert all(isinstance(item, NavPage) for item in navigation.items)


def test_append_unmatched_adds_the_pages_the_nav_forgot(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": "append_unmatched: true\nnav:\n  - second.md\n",
            "first.md": "",
            "second.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == ["second.md", "first.md"]
    assert navigation.unlisted() == ()


def test_hide_removes_a_directory_from_the_navigation(tmp_path: Path):
    write_tree(
        tmp_path,
        {"index.md": "", "internal/.nav.yml": "hide: true\n", "internal/notes.md": ""},
    )
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == ["index.md"]
    assert [page.src_uri for page in navigation.unlisted()] == ["internal/notes.md"]


def test_a_nav_file_in_a_subdirectory_rules_that_subdirectory(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            "guide/.nav.yml": "nav:\n  - zebra.md\n  - alpha.md\n",
            "guide/alpha.md": "",
            "guide/zebra.md": "",
            "other/beta.md": "",
            "other/alpha.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == [
        "guide/zebra.md",
        "guide/alpha.md",
        "other/alpha.md",
        "other/beta.md",
    ]


def test_options_are_inherited_by_subdirectories(tmp_path: Path):
    write_tree(
        tmp_path,
        {
            ".nav.yml": "preserve_directory_names: true\nignore: draft.md\n",
            "my-guide/deep-one/a.md": "",
            "my-guide/deep-one/draft.md": "",
        },
    )
    navigation = resolve_navigation(tmp_path)
    section = navigation.items[0]
    assert isinstance(section, NavSection)
    assert section.title == "my-guide"
    assert titles(section.children) == ["deep-one"]
    assert flat(navigation) == ["my-guide/deep-one/a.md"]


def test_an_unknown_path_in_a_nav_file_is_dropped_with_a_warning(tmp_path: Path, caplog: Any):
    write_tree(tmp_path, {".nav.yml": "nav:\n  - missing.md\n  - real.md\n", "real.md": ""})
    with caplog.at_level("WARNING"):
        navigation = resolve_navigation(tmp_path)
    assert flat(navigation) == ["real.md"]
    assert "missing.md" in caplog.text


@pytest.mark.parametrize(
    ("source", "src_uri", "expected"),
    [
        ("---\ntitle: From Front Matter\n---\n# Heading\n", "a.md", "From Front Matter"),
        ("# First Heading\n\n# Second\n", "a.md", "First Heading"),
        ("# Heading {#anchor}\n", "a.md", "Heading"),
        ("Setext\n======\n", "a.md", "Setext"),
        ("[](){ #anchor }\n# Not The Title\n", "my-page.md", "My page"),
        ("Just a paragraph.\n", "guide/user-guide.md", "User guide"),
        ("", "guide/index.md", "Guide"),
        ("", "index.md", "Home"),
        ("", "README.md", "Home"),
        ("", "guide/Deep_Dive.md", "Deep Dive"),
    ],
)
def test_page_title_follows_mkdocs(tmp_path: Path, source: str, src_uri: str, expected: str):
    write_tree(tmp_path, {src_uri: source})
    assert page_title(NavPage(None, src_uri, tmp_path / src_uri)) == expected


def test_page_title_prefers_the_title_the_navigation_gives(tmp_path: Path):
    write_tree(tmp_path, {"a.md": "---\ntitle: Front Matter\n---\n"})
    assert page_title(NavPage("From Nav", "a.md", tmp_path / "a.md")) == "From Nav"
