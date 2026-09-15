"""The site index: front-matter padding, diagnostics and cross-page numbering.

``texsmith.site.index`` is what a site generator drives, MkDocs or Zensical,
so these tests speak only :class:`SitePage` — no generator is imported.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from texsmith.diagnostics import LoggingEmitter
from texsmith.site import SiteIndex, SitePage
from texsmith.site.index import split_page


log = logging.getLogger("texsmith.site.tests")


def _page(path: Path, src_uri: str) -> SitePage:
    return SitePage(src_uri=src_uri, abs_src_path=path)


def _index(tmp_path: Path) -> SiteIndex:
    return SiteIndex(project_dir=tmp_path, emitter=LoggingEmitter(logger_obj=log))


def test_split_page_counts_the_lines_the_front_matter_occupied() -> None:
    """``padding`` is the number of lines before the body, read off the file."""
    text = "---\ntitle: Demo\nlang: fr\n---\n# Heading\n"
    meta, body, padding = split_page(text)

    assert meta == {"title": "Demo", "lang": "fr"}
    assert body == "# Heading\n"
    # Four lines of front matter (``---``, two keys, ``---``): the body starts
    # on line 5, and padding + body puts it back there.
    assert padding == 4
    assert ("\n" * padding + body).splitlines()[4] == "# Heading"


def test_split_page_handles_the_shapes_the_splitters_disagree_on() -> None:
    """Blank lines after the close, an empty front matter, CRLF, no header."""
    # MkDocs' ``get_data`` eats the blank lines after ``---``; ours keeps them.
    # Either way the body lands on the line the file put it on.
    meta, body, padding = split_page("---\na: 1\n---\n\n\n# T\n")
    assert meta == {"a": 1}
    assert ("\n" * padding + body).splitlines()[5] == "# T"

    # ``---\n---`` parses to no metadata at all, yet took two lines.
    meta, body, padding = split_page("---\n---\n# T\n")
    assert meta == {}
    assert padding == 2
    assert ("\n" * padding + body).splitlines()[2] == "# T"

    meta, _body, padding = split_page("---\r\na: 1\r\n---\r\n# T\r\n")
    assert meta == {"a": 1}
    assert padding == 3

    meta, body, padding = split_page("# T\n\nBody.\n")
    assert (meta, body, padding) == ({}, "# T\n\nBody.\n", 0)


def test_a_diagnostic_on_a_padded_body_reports_the_file_s_line(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """The front matter shifts nothing: line 8 of the file is line 8 of the report.

    A generator hands the extension the body alone; the index pads it back to
    the offset the front matter had, so a diagnostic names the file's line.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    page_path = docs / "intro.md"
    page_path.write_text(
        "---\ntitle: Intro\nlang: en\n---\n\n# Intro\n\nSee @fw:nothing.\n",
        encoding="utf-8",
    )

    index = _index(tmp_path)
    page = _page(page_path, "docs/intro.md")
    _meta, body, padding = split_page(page_path.read_text(encoding="utf-8"))
    # Four lines of front matter; the blank line after it belongs to the body.
    assert padding == 4

    with caplog.at_level(logging.WARNING):
        lowered = index.lower(page, body)
        assert lowered is not None
        index.report(lowered)

    messages = [record.getMessage() for record in caplog.records]
    assert any("docs/intro.md:8:6: warning ref-unresolved:" in message for message in messages)


def test_lowering_reports_a_diagnostic_with_the_page_path(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """A page's diagnostics are logged as ``path:line:col: severity code: message``."""
    page_path = tmp_path / "docs" / "intro.md"
    page_path.parent.mkdir(parents=True)
    page_path.write_text("# Intro\n\nSee @fw:nothing.\n", encoding="utf-8")

    index = _index(tmp_path)
    page = _page(page_path, "docs/intro.md")

    with caplog.at_level(logging.WARNING):
        lowered = index.lower(page, page_path.read_text(encoding="utf-8"))
        assert lowered is not None
        index.report(lowered)

    messages = [record.getMessage() for record in caplog.records]
    assert messages, "Expected the index to log the page's diagnostics"
    # The page path, not the temporary absolute one, and tmark's code.
    assert any("docs/intro.md:3:6: warning ref-unresolved:" in message for message in messages)


def test_every_page_of_a_build_registers_in_one_table(tmp_path: Path) -> None:
    """Two pages of a site take two file ids, so their spans do not collide.

    Each page used to lower against a table of its own and take id 0 in it,
    which made the ``(code, span, message)`` identity of a finding on page two
    equal to the same finding on page one.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    index = _index(tmp_path)

    spans: list[int] = []
    for name in ("first.md", "second.md"):
        path = docs / name
        path.write_text(f"# {name}\n\nSee @fw:nothing.\n", encoding="utf-8")
        lowered = index.lower(_page(path, f"docs/{name}"), path.read_text(encoding="utf-8"))
        assert lowered is not None
        spans.extend(
            record.span.file for record in lowered.diagnostics if record.code == "ref-unresolved"
        )

    assert spans == [0, 1]
    files = index.emitter.sink.files
    # ``files.path()`` holds the page's ``src_uri`` as a ``PurePosixPath``:
    # ``.as_posix()`` is the stable comparison, ``str()`` would be OS-native.
    assert [files.path(index_).as_posix() for index_ in spans] == [
        "docs/first.md",
        "docs/second.md",
    ]


def test_a_page_reaches_a_figure_defined_on_another_page(tmp_path: Path) -> None:
    """The pre-pass chains the numbering, so page B resolves page A's ``@fig:``."""
    docs = tmp_path / "docs"
    docs.mkdir()
    first = docs / "first.md"
    first.write_text(
        "# First\n\n![A kitten](kitten.png){#fig:kitten}\n",
        encoding="utf-8",
    )
    second = docs / "second.md"
    second.write_text("# Second\n\nSee @fig:kitten.\n", encoding="utf-8")

    index = _index(tmp_path)
    pages = [_page(first, "first.md"), _page(second, "second.md")]
    index.prepass(pages)

    assert set(index.records) == {"first.md", "second.md"}
    record = index.record("first.md")
    assert record is not None
    assert {label["key"] for label in record.labels} == {"first", "fig:kitten"}

    lowered = index.lower(pages[1], second.read_text(encoding="utf-8"))
    assert lowered is not None
    assert [item.code for item in lowered.diagnostics] == []
    # The sibling is a link to the other page, carrying the figure's number.
    assert lowered.text == "# Second\n\nSee [Figure 1](first.md#fig:kitten).\n"
