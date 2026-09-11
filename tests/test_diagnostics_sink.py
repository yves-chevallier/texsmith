"""``DiagnosticSink``: dedup, tmark records, ``--strict``, rendering and JSON."""

from __future__ import annotations

from pathlib import Path

from texsmith.diagnostics import (
    NO_SPAN,
    Diagnostic,
    DiagnosticSink,
    FileTable,
    Fix,
    Severity,
    Span,
    format_diagnostic,
    summary_line,
)


def test_emit_defaults_the_severity_from_the_code_table() -> None:
    sink = DiagnosticSink()
    warning = sink.emit("asset-missing", NO_SPAN, "gone")
    info = sink.emit("frontmatter-root-overrides-press", NO_SPAN, "title")
    forced = sink.emit("asset-missing", Span(0, 1, 2), "gone", severity=Severity.ERROR)
    assert warning.severity is Severity.WARNING
    assert info.severity is Severity.INFO
    assert forced.severity is Severity.ERROR
    assert [d.origin for d in sink] == ["texsmith"] * 3


def test_dedup_on_code_span_and_message() -> None:
    sink = DiagnosticSink()
    sink.emit("asset-missing", Span(0, 1, 2), "gone")
    sink.emit("asset-missing", Span(0, 1, 2), "gone")
    sink.emit("asset-missing", Span(0, 1, 2), "gone", severity=Severity.ERROR)
    sink.emit("asset-missing", Span(0, 1, 3), "gone")
    sink.emit("asset-convert-failed", Span(0, 1, 2), "gone")
    sink.emit("asset-missing", Span(0, 1, 2), "still gone")
    assert len(sink) == 4
    assert sink.add(Diagnostic("asset-missing", Severity.WARNING, Span(0, 1, 2), "gone")) is False


def test_on_emit_sees_new_records_and_their_cause() -> None:
    seen: list[tuple[str, BaseException | None]] = []
    sink = DiagnosticSink(on_emit=lambda d, cause: seen.append((d.message, cause)))
    cause = OSError("refused")
    sink.add(Diagnostic("texsmith", Severity.WARNING, NO_SPAN, "fetch"), cause=cause)
    sink.add(Diagnostic("texsmith", Severity.WARNING, NO_SPAN, "fetch"), cause=cause)
    sink.emit("asset-missing", NO_SPAN, "gone")
    assert seen == [("fetch", cause), ("gone", None)]


def test_extend_from_tmark_records() -> None:
    sink = DiagnosticSink()
    records = [
        {"code": "ref-unresolved", "severity": "warning", "span": [0, 20, 31], "message": "a"},
        {"code": "heading-skip", "severity": "hint", "span": [0, 40, 41], "message": "b"},
        {"code": "ref-unresolved", "severity": "warning", "span": [0, 20, 31], "message": "a"},
    ]
    assert sink.extend_from_tmark(records) == 2
    assert [d.origin for d in sink] == ["tmark", "tmark"]
    assert sink.worst() is Severity.WARNING


def test_strict_failed_needs_a_warning_or_an_error() -> None:
    sink = DiagnosticSink()
    assert sink.worst() is None
    assert not sink.strict_failed()
    sink.emit("frontmatter-root-overrides-press", NO_SPAN, "info only")
    sink.emit("heading-skip", NO_SPAN, "hint", severity=Severity.HINT)
    assert not sink.strict_failed()
    sink.emit("asset-missing", NO_SPAN, "gone")
    assert sink.strict_failed()
    assert sink.counts() == {Severity.INFO: 1, Severity.HINT: 1, Severity.WARNING: 1}


def test_summary_line_pluralises() -> None:
    assert summary_line({Severity.ERROR: 1, Severity.WARNING: 2}) == "1 error, 2 warnings"
    assert summary_line({Severity.WARNING: 1}) == "0 errors, 1 warning"
    assert summary_line({}) == "0 errors, 0 warnings"


def test_sorted_groups_per_file_and_position() -> None:
    sink = DiagnosticSink()
    sink.emit("asset-missing", Span(1, 5, 6), "c")
    sink.emit("asset-missing", Span(0, 9, 10), "b")
    sink.emit("asset-missing", NO_SPAN, "a")
    sink.emit("asset-missing", Span(1, 2, 3), "d")
    assert [d.message for d in sink.sorted()] == ["a", "b", "d", "c"]
    assert [d.message for d in sink] == ["c", "b", "a", "d"], "iteration keeps emission order"


def test_to_json_adds_the_printed_location() -> None:
    files = FileTable()
    files.add(Path("doc.md"), "one\ntwo @x\n")
    sink = DiagnosticSink(files)
    sink.emit("ref-unresolved", Span(0, 8, 10), "`@x` does not resolve")
    sink.emit("texsmith", NO_SPAN, "engine failed", severity=Severity.ERROR)
    sink.emit("texsmith", Span(4, 0, 0), "unknown file")
    payload = sink.to_json()
    assert payload == [
        {
            "code": "texsmith",
            "severity": "error",
            "span": [0, 0, 0],
            "message": "engine failed",
            "origin": "texsmith",
            "path": "doc.md",
            "line": None,
            "col": None,
        },
        {
            "code": "ref-unresolved",
            "severity": "warning",
            "span": [0, 8, 10],
            "message": "`@x` does not resolve",
            "origin": "texsmith",
            "path": "doc.md",
            "line": 2,
            "col": 5,
        },
        {
            "code": "texsmith",
            "severity": "warning",
            "span": [4, 0, 0],
            "message": "unknown file",
            "origin": "texsmith",
            "path": None,
            "line": None,
            "col": None,
        },
    ]


def test_format_diagnostic_shows_fix_and_related_at_verbosity_one() -> None:
    files = FileTable()
    files.add(Path("doc.md"), "see [^k] and [^k]: note\n")
    diagnostic = Diagnostic(
        "deprecated",
        Severity.WARNING,
        Span(0, 4, 8),
        "`[^k]` is a citation; write `@k`",
        fix=Fix(Span(0, 4, 8), "@k"),
        related=((Span(0, 13, 17), "the footnote definition"),),
        origin="tmark",
    )
    plain = "doc.md:1:5: warning deprecated: `[^k]` is a citation; write `@k`"
    assert format_diagnostic(diagnostic, files) == plain
    assert format_diagnostic(diagnostic, files, verbosity=1) == "\n".join(
        [
            plain,
            "  fix at doc.md:1:5: replace with '@k'",
            "  doc.md:1:14: the footnote definition",
        ]
    )


def test_format_diagnostic_indents_a_multiline_message() -> None:
    diagnostic = Diagnostic("texsmith", Severity.WARNING, NO_SPAN, "Fetch failed\ntype: OSError")
    assert format_diagnostic(diagnostic, FileTable()) == (
        "warning texsmith: Fetch failed\n  type: OSError"
    )
