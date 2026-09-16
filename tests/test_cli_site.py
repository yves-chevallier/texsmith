"""The ``texsmith site`` group, through Typer's runner.

The root command still takes a document straight from the command line; the
group is reached only by its own name.
"""

from __future__ import annotations

import json
from pathlib import Path
import textwrap
from typing import Any

import pytest
from typer.testing import CliRunner

from texsmith.adapters.plugins import snippet
from texsmith.site import assets
from texsmith.ui.cli import app


MKDOCS_YML = """\
site_name: Test site
nav:
  - Home: index.md
  - Guide: guide/a.md
"""

PAGE_WITH_FENCE = textwrap.dedent("""\
    # A

    ```md {.snippet}
    Hello
    ```
    """)


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A two-page site whose previews are recorded instead of built."""
    (tmp_path / "mkdocs.yml").write_text(MKDOCS_YML, encoding="utf-8")
    docs = tmp_path / "docs"
    (docs / "guide").mkdir(parents=True)
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    (docs / "guide" / "a.md").write_text(PAGE_WITH_FENCE, encoding="utf-8")

    def record(block: snippet.SnippetBlock, **kwargs: Any) -> None:
        del block, kwargs

    monkeypatch.setattr(snippet, "ensure_snippet_assets", record)
    return tmp_path


def test_the_command_writes_the_generated_sources_and_says_so(site: Path) -> None:
    result = CliRunner().invoke(app, ["site", "assets", str(site / "mkdocs.yml")])

    assert result.exit_code == 0, result.output
    assert "guide/a.md" in result.output
    assert "1 snippet previews" in result.output
    assert (site / "docs" / assets.CSS_URI).is_file()


def test_the_configuration_file_is_found_in_the_current_directory(
    site: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(site)

    result = CliRunner().invoke(app, ["site", "assets"])

    assert result.exit_code == 0, result.output
    assert (site / "docs" / assets.CSS_URI).is_file()


def test_a_directory_without_a_configuration_file_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["site", "assets"])

    assert result.exit_code == 1


def test_a_stale_preview_is_reported_as_pruned(site: Path) -> None:
    previews = site / "docs" / "assets" / "snippets"
    previews.mkdir(parents=True)
    (previews / "snippet-stale.pdf").write_text("x", encoding="utf-8")

    result = CliRunner().invoke(app, ["site", "assets", str(site / "mkdocs.yml")])

    assert "pruned snippet-stale.pdf" in result.output
    assert not (previews / "snippet-stale.pdf").exists()


def test_the_group_does_not_take_the_root_command_away() -> None:
    """``texsmith doc.md`` is still the whole command line it has always been."""
    result = CliRunner().invoke(app, ["--help"], prog_name="texsmith")

    assert result.exit_code == 0
    assert "Usage: texsmith [OPTIONS] [INPUT...]" in result.output
    assert "texsmith site" in result.output


SEARCH_PAGE = """\
<h1 id="a">A<a class="headerlink" href="#a" title="Permanent link">&para;</a></h1>
<p>Text <span class="ts-index" data-tag="cake"></span>.</p>
"""


def built_site(root: Path) -> Path:
    """A built site holding one page with an index entry and MkDocs' lunr index."""
    site_dir = root / "site"
    (site_dir / "guide" / "a").mkdir(parents=True)
    (site_dir / "guide" / "a" / "index.html").write_text(SEARCH_PAGE, encoding="utf-8")
    lunr = site_dir / "search" / "search_index.json"
    lunr.parent.mkdir(parents=True)
    lunr.write_text(
        json.dumps({"config": {}, "docs": [{"location": "guide/a/", "text": "Body."}]}),
        encoding="utf-8",
    )
    return site_dir


def test_the_search_command_patches_the_index_of_the_built_site(site: Path) -> None:
    site_dir = built_site(site)

    result = CliRunner().invoke(app, ["site", "search", str(site / "mkdocs.yml")])

    assert result.exit_code == 0, result.output
    assert "1 search entries" in result.output
    index = json.loads((site_dir / "search" / "search_index.json").read_text(encoding="utf-8"))
    assert index["docs"][0]["tags"] == ["cake"]


def test_the_index_a_zensical_build_wrote_is_not_touched(site: Path) -> None:
    """``search.json`` carries the terms as a page's ``tags``, written at render time."""
    site_dir = site / "site"
    (site_dir / "guide" / "a").mkdir(parents=True)
    (site_dir / "guide" / "a" / "index.html").write_text(SEARCH_PAGE, encoding="utf-8")
    index = site_dir / "search.json"
    index.write_text(
        json.dumps({"config": {}, "items": [{"location": "guide/a/", "text": "<p>Body.</p>"}]}),
        encoding="utf-8",
    )
    before = index.read_text(encoding="utf-8")

    result = CliRunner().invoke(app, ["site", "search", str(site / "mkdocs.yml")])

    assert result.exit_code == 0, result.output
    assert "No lunr index" in result.output
    assert index.read_text(encoding="utf-8") == before


def test_the_search_command_needs_a_built_site(site: Path) -> None:
    result = CliRunner().invoke(app, ["site", "search", str(site / "mkdocs.yml")])

    assert result.exit_code == 1


def test_a_site_without_index_entries_is_left_alone(site: Path) -> None:
    site_dir = site / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("<p>Nothing.</p>", encoding="utf-8")

    result = CliRunner().invoke(app, ["site", "search", str(site / "mkdocs.yml")])

    assert result.exit_code == 0, result.output
    assert "No index entries" in result.output


def test_the_build_command_writes_the_book_and_says_where_it_landed(site: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["site", "build", str(site / "mkdocs.yml"), "--build-dir", str(site / "out"), "--no-pdf"],
    )

    assert result.exit_code == 0, result.output
    assert "out/index.tex" in result.output
    assert (site / "out" / "index.tex").is_file()
    assert (site / "out" / "pages" / "index-md.tex").is_file()


def test_the_build_command_reports_a_book_nobody_declared(site: Path) -> None:
    result = CliRunner().invoke(
        app, ["site", "build", str(site / "mkdocs.yml"), "--book", "Nowhere", "--no-pdf"]
    )

    assert result.exit_code == 1
