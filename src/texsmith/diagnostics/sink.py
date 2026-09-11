"""The collector every stage emits into, and the one rendering of a record.

A :class:`DiagnosticSink` deduplicates on ``(code, span, message)``, keeps the
records in emission order and answers ``strict_failed()`` for ``--strict``.
:func:`format_diagnostic` prints the ``tmark-cli`` line —
``{path}:{line}:{col}: {severity} {code}: {message}`` — so both tools print
identical lines for identical findings.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any

from .codes import default_severity
from .files import FileTable
from .model import NO_SPAN, Diagnostic, Fix, Severity, Span, from_tmark


#: Called with each *new* record and the exception that caused it, if any. The
#: exception is rendering context (``-v`` shows it), never part of the record.
OnEmit = Callable[[Diagnostic, BaseException | None], None]


class DiagnosticSink:
    """Collects diagnostics for one run.

    ``files`` is the table spans render against; passes and the loader share
    it with the sink so a record emitted in an included file prints that
    file's name.
    """

    __slots__ = ("_index", "_on_emit", "_records", "files")

    def __init__(self, files: FileTable | None = None, *, on_emit: OnEmit | None = None) -> None:
        self.files = files if files is not None else FileTable()
        self._records: list[Diagnostic] = []
        self._index: set[tuple[str, Span, str]] = set()
        self._on_emit = on_emit

    def add(self, diagnostic: Diagnostic, *, cause: BaseException | None = None) -> bool:
        """Record ``diagnostic``; ``False`` when an identical record exists."""
        if diagnostic.key in self._index:
            return False
        self._index.add(diagnostic.key)
        self._records.append(diagnostic)
        if self._on_emit is not None:
            self._on_emit(diagnostic, cause)
        return True

    def emit(
        self,
        code: str,
        span: Span,
        message: str,
        *,
        severity: Severity | None = None,
        fix: Fix | None = None,
        related: Iterable[tuple[Span, str]] = (),
    ) -> Diagnostic:
        """Build and record a TeXSmith diagnostic, severity defaulting from the code table."""
        diagnostic = Diagnostic(
            code=code,
            severity=severity if severity is not None else default_severity(code),
            span=span,
            message=message,
            fix=fix,
            related=tuple(related),
        )
        self.add(diagnostic)
        return diagnostic

    def extend_from_tmark(self, records: Iterable[Mapping[str, Any]]) -> int:
        """Record the diagnostics of a tmark result; returns how many were new."""
        return sum(1 for record in records if self.add(from_tmark(record)))

    def strict_failed(self) -> bool:
        """Whether any warning or error was recorded (``--strict`` fails the run)."""
        return any(record.severity >= Severity.WARNING for record in self._records)

    def worst(self) -> Severity | None:
        """The highest severity recorded, ``None`` when the sink is empty."""
        return max((record.severity for record in self._records), default=None)

    def counts(self) -> Counter[Severity]:
        return Counter(record.severity for record in self._records)

    def sorted(self) -> list[Diagnostic]:
        """The records grouped per file and ordered by position."""
        return sorted(self._records, key=sort_key)

    def to_json(self) -> list[dict[str, Any]]:
        """The records for editors and CI: tmark's shape plus the printed location."""
        payload: list[dict[str, Any]] = []
        for record in self.sorted():
            entry = record.to_json()
            location = locate(record.span, self.files)
            entry["path"] = str(location[0]) if location is not None else None
            entry["line"] = location[1] if location is not None else None
            entry["col"] = location[2] if location is not None else None
            payload.append(entry)
        return payload

    def __iter__(self) -> Iterator[Diagnostic]:
        return iter(tuple(self._records))

    def __len__(self) -> int:
        return len(self._records)


def sort_key(diagnostic: Diagnostic) -> tuple[int, int]:
    return (diagnostic.span.file, diagnostic.span.start)


def locate(span: Span, files: FileTable) -> tuple[Any, int | None, int | None] | None:
    """``(path, line, col)`` of a span; line and col are ``None`` without a text.

    ``NO_SPAN`` names the main document without a position; an unknown file
    yields ``None`` and the record prints without a path.
    """
    entry = files.get(span.file)
    if entry is None:
        return None
    if span == NO_SPAN or not entry.text:
        return (entry.path, None, None)
    position = entry.line_index.line_col(span.start)
    return (entry.path, position.line, position.col)


def _location_prefix(span: Span, files: FileTable) -> str:
    location = locate(span, files)
    if location is None:
        return ""
    path, line, col = location
    if line is None:
        return f"{path}: "
    return f"{path}:{line}:{col}: "


def format_diagnostic(diagnostic: Diagnostic, files: FileTable, *, verbosity: int = 0) -> str:
    """The ``tmark-cli`` line; the fix and the related locations indented at ``-v``.

    A multi-line message keeps its first line on the header and indents the
    rest, so the detail an emitter appends (``-v`` exception notes) stays
    attached to its record.
    """
    first, _, rest = diagnostic.message.partition("\n")
    lines = [
        f"{_location_prefix(diagnostic.span, files)}"
        f"{diagnostic.severity.value} {diagnostic.code}: {first}"
    ]
    lines.extend(f"  {line}" for line in rest.splitlines())
    if verbosity >= 1:
        if diagnostic.fix is not None:
            where = _location_prefix(diagnostic.fix.span, files).rstrip(": ")
            target = f" at {where}" if where else ""
            lines.append(f"  fix{target}: replace with {diagnostic.fix.replacement!r}")
        for span, label in diagnostic.related:
            lines.append(f"  {_location_prefix(span, files)}{label}")
    return "\n".join(lines)


def summary_line(counts: Mapping[Severity, int]) -> str:
    """``N errors, M warnings`` — singular when it applies."""
    errors = counts.get(Severity.ERROR, 0)
    warnings = counts.get(Severity.WARNING, 0)
    return (
        f"{errors} error{'' if errors == 1 else 's'}, "
        f"{warnings} warning{'' if warnings == 1 else 's'}"
    )


__all__ = [
    "DiagnosticSink",
    "OnEmit",
    "format_diagnostic",
    "locate",
    "sort_key",
    "summary_line",
]
