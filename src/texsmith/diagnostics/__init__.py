"""Diagnostics shared by TeXSmith's Python passes and the tmark bindings.

See ``specs/migration/python-ir-and-passes.md`` §6 and ``docs/guide/diagnostics.md``.
"""

from __future__ import annotations

from .codes import CODES, CodeInfo, default_severity
from .files import FileId, FileTable, LineCol, LineIndex, SourceFile
from .model import NO_SPAN, Diagnostic, Fix, Severity, Span, from_tmark
from .sink import DiagnosticSink, format_diagnostic, locate, sort_key, summary_line


__all__ = [
    "CODES",
    "NO_SPAN",
    "CodeInfo",
    "Diagnostic",
    "DiagnosticSink",
    "FileId",
    "FileTable",
    "Fix",
    "LineCol",
    "LineIndex",
    "Severity",
    "SourceFile",
    "Span",
    "default_severity",
    "format_diagnostic",
    "from_tmark",
    "locate",
    "sort_key",
    "summary_line",
]
