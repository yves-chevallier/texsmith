"""``FileTable`` and ``LineIndex``: the positions TeXSmith prints match ``tmark check``."""

from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.diagnostics import (
    NO_SPAN,
    Diagnostic,
    FileTable,
    LineCol,
    LineIndex,
    Severity,
    Span,
    format_diagnostic,
)


#: A scratch file run through ``tmark check`` (tmark-cli, 2026-09-11). Each
#: ``@key`` is unresolved; tmark reports it at the key's span, which starts
#: after the ``@``. The three lines below are what it printed, verbatim, with
#: the file name shortened.
PROBE_TEXT = "Заголовок @fig:missing здесь\n\nemoji 😀 @tbl:nope end\n\nplain @sec:x\n"
PROBE_MESSAGE = "does not resolve to a label, a citation key, a glossary term or an inventory"
TMARK_CHECK_LINES = [
    f"probe.md:1:21: warning ref-unresolved: `@fig:missing` {PROBE_MESSAGE}",
    f"probe.md:3:13: warning ref-unresolved: `@tbl:nope` {PROBE_MESSAGE}",
    f"probe.md:5:8: warning ref-unresolved: `@sec:x` {PROBE_MESSAGE}",
]


def _key_offset(key: str) -> int:
    return PROBE_TEXT.encode("utf-8").index(key.encode("utf-8"))


def test_cyrillic_and_emoji_lines_print_tmark_columns() -> None:
    files = FileTable()
    file_id = files.add(Path("probe.md"), PROBE_TEXT)
    rendered = []
    for key in ("fig:missing", "tbl:nope", "sec:x"):
        start = _key_offset(key)
        diagnostic = Diagnostic(
            "ref-unresolved",
            Severity.WARNING,
            Span(file_id, start, start + len(key)),
            f"`@{key}` {PROBE_MESSAGE}",
            origin="tmark",
        )
        rendered.append(format_diagnostic(diagnostic, files))
    assert rendered == TMARK_CHECK_LINES


def test_line_col_is_one_based_bytes() -> None:
    index = LineIndex("ab\ncd\n\nef")
    assert index.line_count == 4
    assert index.line_col(0) == LineCol(1, 1)
    assert index.line_col(2) == LineCol(1, 3)  # the ``\n`` itself
    assert index.line_col(3) == LineCol(2, 1)
    assert index.line_col(6) == LineCol(3, 1)
    assert index.line_col(7) == LineCol(4, 1)
    assert index.line_col(9) == LineCol(4, 3)
    assert index.line_col(99) == LineCol(4, 3), "clamps to the end of the text"
    assert len(index) == 9


def test_multibyte_columns_count_bytes_and_snap_inside_a_character() -> None:
    # "é" is 2 bytes, "€" 3, "😀" 4.
    text = "aé€😀b\nxyz"
    index = LineIndex(text)
    b = text.encode("utf-8").index(b"b")
    assert b == 1 + 2 + 3 + 4
    assert index.line_col(b) == LineCol(1, 11)
    # Inside the emoji: snaps to its first byte.
    for inside in (7, 8, 9):
        assert index.line_col(inside) == LineCol(1, 7)
    # Inside "é": snaps back to it.
    assert index.line_col(2) == LineCol(1, 2)
    assert index.line_col(len(text.encode())) == LineCol(2, 4)


def test_crlf_and_lone_cr_are_line_breaks() -> None:
    index = LineIndex("a\r\nb\rc\n")
    assert index.line_count == 4
    assert index.line_start(2) == 3
    assert index.line_start(3) == 5
    assert index.line_start(4) == 7
    assert index.line_start(5) is None
    assert index.line_col(4) == LineCol(2, 2)
    assert index.line_end(1) == 1
    assert index.line_end(2) == 4
    assert index.line_end(4) == 7


def test_offset_clamps_before_the_line_break() -> None:
    index = LineIndex("é\nb\r\nc")
    assert index.line_end(1) == 2
    assert index.line_end(2) == 4
    assert index.line_end(3) == 7
    assert index.offset(LineCol(1, 7)) == 2, "before the \\n"
    assert index.offset(LineCol(2, 10)) == 4, "before the \\r\\n"
    assert index.offset(LineCol(2, 2)) == 4
    assert index.offset(LineCol(3, 10)) == 7
    assert index.offset(LineCol(8, 1)) == 7, "a line past the text clamps to its end"
    assert index.offset(index.line_col(3)) == 3, "round trip"


def test_empty_text_has_one_line() -> None:
    index = LineIndex("")
    assert index.line_count == 1
    assert index.line_col(0) == LineCol(1, 1)
    assert index.line_col(5) == LineCol(1, 1)
    assert index.line_end(1) == 0


def test_file_table_numbers_files_in_order() -> None:
    files = FileTable()
    assert len(files) == 0
    main = files.add(Path("doc.md"), "# Title\n")
    included = files.add("parts/intro.md", "Intro\n")
    assert (main, included) == (0, 1)
    assert list(files) == [0, 1]
    assert files.path(included) == Path("parts/intro.md")
    assert files.text(main) == "# Title\n"
    assert files.line_index(main) is files.line_index(main), "the index is cached"
    assert files.find("parts/intro.md") == included
    assert files.find(Path("absent.md")) is None
    assert 1 in files
    assert 2 not in files
    assert files.get(2) is None
    with pytest.raises(KeyError):
        files.path(2)


def test_no_span_and_text_less_files_print_the_path_only() -> None:
    files = FileTable()
    files.add(Path("doc.md"), "# Title\n")
    html = files.add(Path("page.html"), "")
    located = Diagnostic("asset-missing", Severity.WARNING, NO_SPAN, "gone")
    assert format_diagnostic(located, files) == "doc.md: warning asset-missing: gone"
    in_html = Diagnostic("asset-missing", Severity.WARNING, Span(html, 40, 44), "gone")
    assert format_diagnostic(in_html, files) == "page.html: warning asset-missing: gone"
    unknown = Diagnostic("texsmith", Severity.ERROR, Span(7, 0, 0), "engine failed")
    assert format_diagnostic(unknown, files) == "error texsmith: engine failed"
    assert format_diagnostic(unknown, FileTable()) == "error texsmith: engine failed"
