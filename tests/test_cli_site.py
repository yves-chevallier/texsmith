"""The ``texsmith site`` group, through Typer's runner.

The root command still takes a document straight from the command line; the
group is reached only by its own name.
"""

from __future__ import annotations

from pathlib import Path
import re
import textwrap
from typing import Any

import pytest
from typer.testing import CliRunner

from texsmith.adapters.plugins import snippet
from texsmith.site import assets
from texsmith.ui.cli import app


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(result: object) -> str:
    """The command's output without Rich's colour codes (CI sets FORCE_COLOR)."""
    return _ANSI.sub("", result.output)


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

    assert result.exit_code == 0, _plain(result)
    assert "guide/a.md" in _plain(result)
    assert "1 snippet previews" in _plain(result)
    assert (site / "docs" / assets.CSS_URI).is_file()


def test_the_configuration_file_is_found_in_the_current_directory(
    site: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(site)

    result = CliRunner().invoke(app, ["site", "assets"])

    assert result.exit_code == 0, _plain(result)
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

    assert "pruned snippet-stale.pdf" in _plain(result)
    assert not (previews / "snippet-stale.pdf").exists()


def test_the_group_does_not_take_the_root_command_away() -> None:
    """``texsmith doc.md`` is still the whole command line it has always been."""
    result = CliRunner().invoke(app, ["--help"], prog_name="texsmith")

    output = _plain(result)
    assert result.exit_code == 0
    assert "Usage: texsmith [OPTIONS] [INPUT...]" in output
    assert "texsmith site" in output


def test_the_build_command_writes_the_book_and_says_where_it_landed(site: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["site", "build", str(site / "mkdocs.yml"), "--build-dir", str(site / "out"), "--no-pdf"],
    )

    assert result.exit_code == 0, _plain(result)
    assert "out/index.tex" in _plain(result)
    assert (site / "out" / "index.tex").is_file()
    assert (site / "out" / "pages" / "index-md.tex").is_file()


def test_the_build_command_reports_a_book_nobody_declared(site: Path) -> None:
    result = CliRunner().invoke(
        app, ["site", "build", str(site / "mkdocs.yml"), "--book", "Nowhere", "--no-pdf"]
    )

    assert result.exit_code == 1
