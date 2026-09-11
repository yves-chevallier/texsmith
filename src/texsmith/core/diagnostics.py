"""Diagnostic abstractions shared across the conversion pipeline.

Every emitter collects :class:`~texsmith.diagnostics.Diagnostic` records in a
:class:`~texsmith.diagnostics.DiagnosticSink` and renders them its own way:
the CLI prints ``file:line:col: severity code: message``, the logging emitter
forwards the same line to :mod:`logging`. The legacy ``warning()``/``error()``
calls build a record with the free-form ``texsmith`` code and no location, so
engine and network messages share the collector with the passes.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
import logging
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from texsmith.diagnostics import (
    LEGACY_CODE,
    NO_SPAN,
    Diagnostic,
    DiagnosticSink,
    FileTable,
    Severity,
    Span,
    default_severity,
    format_diagnostic,
)


logger = logging.getLogger(__name__)


@runtime_checkable
class DiagnosticEmitter(Protocol):
    """Interface used to surface warnings, errors, and structured events."""

    debug_enabled: bool

    def warning(self, message: str, exc: BaseException | None = None) -> None: ...

    def error(self, message: str, exc: BaseException | None = None) -> None: ...

    def event(self, name: str, payload: Mapping[str, Any]) -> None: ...

    def diagnostic(self, diagnostic: Diagnostic) -> None: ...


class NullEmitter:
    """Emitter that ignores every diagnostic."""

    debug_enabled: bool = False

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        return

    def error(self, message: str, exc: BaseException | None = None) -> None:
        return

    def event(self, name: str, payload: Mapping[str, Any]) -> None:
        return

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        return


class SinkEmitter:
    """Base of the emitters that collect: owns the sink, renders each new record.

    Subclasses implement :meth:`render` (and :meth:`event`). ``warning()`` and
    ``error()`` are the legacy entry points: a record with the ``texsmith``
    code and no location, the exception kept as rendering context only.
    """

    debug_enabled: bool

    def __init__(self, *, debug_enabled: bool = False, files: FileTable | None = None) -> None:
        self.debug_enabled = debug_enabled
        self.sink = DiagnosticSink(files, on_emit=self.render)

    @property
    def files(self) -> FileTable:
        return self.sink.files

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        self.sink.add(diagnostic)

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        self.sink.add(legacy_diagnostic(Severity.WARNING, message), cause=exc)

    def error(self, message: str, exc: BaseException | None = None) -> None:
        self.sink.add(legacy_diagnostic(Severity.ERROR, message), cause=exc)

    def event(self, name: str, payload: Mapping[str, Any]) -> None:
        raise NotImplementedError

    def render(self, diagnostic: Diagnostic, cause: BaseException | None) -> None:
        raise NotImplementedError


def legacy_diagnostic(severity: Severity, message: str) -> Diagnostic:
    """The record of a ``warning()``/``error()`` call: free-form code, no location."""
    return Diagnostic(LEGACY_CODE, severity, NO_SPAN, message)


_LOG_LEVELS = {
    Severity.HINT: logging.DEBUG,
    Severity.INFO: logging.INFO,
    Severity.WARNING: logging.WARNING,
    Severity.ERROR: logging.ERROR,
}


class LoggingEmitter(SinkEmitter):
    """Emitter that forwards diagnostics to the standard logging module."""

    def __init__(
        self,
        *,
        logger_obj: logging.Logger | None = None,
        debug_enabled: bool = False,
        files: FileTable | None = None,
    ) -> None:
        super().__init__(debug_enabled=debug_enabled, files=files)
        self._logger = logger_obj or logger

    def render(self, diagnostic: Diagnostic, cause: BaseException | None) -> None:
        self._logger.log(
            _LOG_LEVELS[diagnostic.severity],
            format_diagnostic(diagnostic, self.files),
            exc_info=cause,
        )

    def event(self, name: str, payload: Mapping[str, Any]) -> None:
        message = format_event_message(name, payload)
        if message:
            self._logger.info(message)
            return
        try:
            self._logger.debug("diagnostic event %s: %s", name, dict(payload))
        except Exception:  # pragma: no cover - defensive
            self._logger.debug("failed to log diagnostic event %s", name, exc_info=True)


_ACTIVE_EMITTER: ContextVar[DiagnosticEmitter | None] = ContextVar(
    "texsmith_active_emitter", default=None
)


@contextmanager
def use_emitter(emitter: DiagnosticEmitter | None) -> Iterator[None]:
    """Make ``emitter`` the target of :func:`emit_diagnostic` for the block.

    ``None`` installs nothing: code running outside a conversion keeps the
    logging fallback, so an authoring defect never goes unreported.
    """
    if emitter is None:
        yield
        return
    token = _ACTIVE_EMITTER.set(emitter)
    try:
        yield
    finally:
        _ACTIVE_EMITTER.reset(token)


def current_emitter() -> DiagnosticEmitter:
    """The emitter installed by :func:`use_emitter`, else a fresh :class:`LoggingEmitter`."""
    active = _ACTIVE_EMITTER.get()
    return active if active is not None else LoggingEmitter()


def emit_diagnostic(
    code: str,
    message: str,
    *,
    span: Span = NO_SPAN,
    severity: Severity | None = None,
    origin: Path | str | None = None,
) -> Diagnostic:
    """Report a finding from code that holds no emitter (the Markdown extensions).

    ``origin`` names the document a location-less finding belongs to: it is
    registered in the emitter's file table (without text) so the record prints
    as ``doc.md: warning code: message``. Emitters that do not collect keep the
    bare record.
    """
    emitter = current_emitter()
    if origin is not None and span == NO_SPAN and isinstance(emitter, SinkEmitter):
        file_id = emitter.files.find(origin)
        if file_id is None:
            file_id = emitter.files.add(origin, "")
        span = Span(file_id, 0, 0)
    diagnostic = Diagnostic(
        code=code,
        severity=severity if severity is not None else default_severity(code),
        span=span,
        message=message,
    )
    emitter.diagnostic(diagnostic)
    return diagnostic


def format_event_message(name: str, payload: Mapping[str, Any]) -> str | None:
    """Return a human-friendly summary for selected diagnostic events."""
    try:
        data = dict(payload)
    except Exception:  # pragma: no cover - defensive
        data = {}

    if name == "asset_fetch":
        url = data.get("url") or "<unknown>"
        convert = data.get("convert")
        suffix_hint = data.get("suffix_hint")
        details: list[str] = []
        if convert:
            details.append("convert")
        if suffix_hint:
            details.append(f"suffix={suffix_hint}")
        suffix = f" ({', '.join(details)})" if details else ""
        return f"Fetching: {url}{suffix}"

    if name == "asset_fetch_cached":
        url = data.get("url") or "<unknown>"
        reason = data.get("reason") or "cache"
        return f"Reusing cached remote image: {url} ({reason})"

    if name == "doi_fetch":
        doi_value = data.get("value") or data.get("doi") or "<unknown>"
        key = data.get("key") or "<unknown>"
        mode = data.get("mode")
        source = data.get("source") or data.get("resolved_source")
        details: list[str] = []
        if mode:
            details.append(str(mode))
        if source:
            details.append(str(source))
        suffix = f" ({', '.join(details)})" if details else ""
        return f"Resolved DOI {doi_value} for entry '{key}'{suffix}"

    return None


__all__ = [
    "DiagnosticEmitter",
    "LoggingEmitter",
    "NullEmitter",
    "SinkEmitter",
    "current_emitter",
    "emit_diagnostic",
    "format_event_message",
    "legacy_diagnostic",
    "use_emitter",
]
