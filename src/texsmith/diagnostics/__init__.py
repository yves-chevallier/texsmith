"""Diagnostics shared by TeXSmith's Python passes and the tmark bindings.

See ``specs/migration/python-ir-and-passes.md`` §6 and ``docs/guide/diagnostics.md``.
"""

from __future__ import annotations

from .codes import CODES, CodeInfo, default_severity
from .emitters import (
    DiagnosticEmitter,
    LoggingEmitter,
    NullEmitter,
    SinkEmitter,
    debug_enabled,
    emit_diagnostic,
    ensure_emitter,
    format_event_message,
    record_event,
)
from .files import FileId, FileTable, LineCol, LineIndex, SourceFile
from .model import NO_SPAN, Diagnostic, Fix, Severity, Span, from_tmark
from .sink import DiagnosticSink, format_diagnostic, locate, sort_key, summary_line


__all__ = [
    "CODES",
    "NO_SPAN",
    "CodeInfo",
    "Diagnostic",
    "DiagnosticEmitter",
    "DiagnosticSink",
    "FileId",
    "FileTable",
    "Fix",
    "LineCol",
    "LineIndex",
    "LoggingEmitter",
    "NullEmitter",
    "Severity",
    "SinkEmitter",
    "SourceFile",
    "Span",
    "debug_enabled",
    "default_severity",
    "emit_diagnostic",
    "ensure_emitter",
    "format_diagnostic",
    "format_event_message",
    "from_tmark",
    "locate",
    "record_event",
    "sort_key",
    "summary_line",
]
