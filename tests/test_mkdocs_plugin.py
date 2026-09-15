"""The plugin as an adapter: MkDocs' navigation as the book builder reads it.

The book itself is ``texsmith.site.book``'s (``tests/test_site_book.py``); what
the plugin still owns is the conversion of MkDocs' own ``Navigation`` into the
:mod:`texsmith.site.nav` tree, which has to agree with what the resolver
produces for the same tree — otherwise the book of a Zensical build and the
book of an MkDocs build would not have the same chapters.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.core.config import BookConfig
from texsmith.site.book import flatten_navigation, item_title
from texsmith.site.config import load_site_config
from texsmith.site.nav import NavLink, NavPage, NavSection, resolve_navigation


mkdocs = pytest.importorskip("mkdocs", reason="MkDocs is not installed")

from mkdocs.commands.build import build as mkdocs_build  # noqa: E402
from mkdocs.config import load_config  # noqa: E402
from mkdocs.structure.files import get_files  # noqa: E402
from mkdocs.structure.nav import get_navigation  # noqa: E402
from mkdocs_plugin_texsmith.plugin import _nav_items  # noqa: E402


MKDOCS_YML = """\
site_name: A site
plugins: []
nav:
  - Home: index.md
  - Guide:
      - Guide: guide/index.md
      - One: guide/one.md
  - Elsewhere: https://example.org
"""

PAGES = {
    "index.md": "# Home\n",
    "guide/index.md": "# Guide\n",
    "guide/one.md": "# One\n",
}


@pytest.fixture
def site(tmp_path: Path) -> Path:
    (tmp_path / "mkdocs.yml").write_text(MKDOCS_YML, encoding="utf-8")
    for src_uri, body in PAGES.items():
        path = tmp_path / "docs" / src_uri
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return tmp_path


def mkdocs_navigation(site: Path):
    config = load_config(str(site / "mkdocs.yml"))
    files = get_files(config)
    return get_navigation(files, config)


def shape(items: tuple) -> list:
    """Each item as its kind, its title and, for a page, its source."""
    rows = []
    for item in items:
        if isinstance(item, NavPage):
            rows.append(("page", item_title(item), item.src_uri))
        elif isinstance(item, NavLink):
            rows.append(("link", item.title, item.url))
        elif isinstance(item, NavSection):
            rows.append(("section", item.title, shape(item.children)))
    return rows


def resolved_navigation(site: Path) -> tuple:
    """The same ``nav:``, resolved the way ``texsmith site build`` resolves it."""
    config = load_site_config(site / "mkdocs.yml")
    return resolve_navigation(config.docs_dir, config.nav).items


def test_the_conversion_keeps_a_section_index_where_mkdocs_keeps_it(site: Path) -> None:
    converted = _nav_items(mkdocs_navigation(site).items)

    # The resolver promotes a section's index page to the section itself; the
    # conversion leaves it where MkDocs keeps it, among the children. Both
    # flatten to the same chapters, which is what the book is made of.
    assert shape(converted) == [
        ("page", "Home", "index.md"),
        (
            "section",
            "Guide",
            [("page", "Guide", "guide/index.md"), ("page", "One", "guide/one.md")],
        ),
        ("link", "Elsewhere", "https://example.org"),
    ]
    assert shape(resolved_navigation(site)) == [
        ("page", "Home", "index.md"),
        ("section", "Guide", [("page", "One", "guide/one.md")]),
        ("link", "Elsewhere", "https://example.org"),
    ]


def test_both_navigations_flatten_to_the_same_chapters(site: Path) -> None:
    def chapters(items: tuple) -> list:
        entries = []
        for item in items:
            entries.extend(flatten_navigation(item, BookConfig(base_level=0)))
        return [(entry.title, entry.level, entry.is_page, entry.src_uri) for entry in entries]

    converted = chapters(_nav_items(mkdocs_navigation(site).items))
    resolved = chapters(resolved_navigation(site))

    assert converted == resolved
    assert converted == [
        ("Home", 0, True, "index.md"),
        ("Guide", 0, False, None),
        ("Guide", 1, True, "guide/index.md"),
        ("One", 1, True, "guide/one.md"),
        ("Elsewhere", 0, False, None),
    ]


def test_a_page_mkdocs_made_up_has_no_source_and_is_left_out(site: Path) -> None:
    navigation = mkdocs_navigation(site)
    page = navigation.pages[0]
    page.file.abs_src_path = None

    assert [
        item.src_uri for item in _nav_items(navigation.items) if isinstance(item, NavPage)
    ] == []


def test_the_plugin_builds_the_book_of_a_site(site: Path) -> None:
    """The whole hook chain, from ``on_config`` to the ``.tex`` of ``on_post_build``."""
    (site / "mkdocs.yml").write_text(
        MKDOCS_YML.replace(
            "plugins: []",
            "plugins:\n  - texsmith:\n      build_dir: press\n",
        ),
        encoding="utf-8",
    )
    config = load_config(str(site / "mkdocs.yml"), site_dir=str(site / "site"))
    config.plugins.on_startup(command="build", dirty=False)

    mkdocs_build(config)

    assert (site / "press" / "index.tex").is_file()
    assert (site / "press" / "sources" / "index.md").is_file()
