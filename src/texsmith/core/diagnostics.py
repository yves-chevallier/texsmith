"""Diagnostic abstractions shared across the conversion pipeline.

Every emitter collects :class:`~texsmith.diagnostics.Diagnostic` records in a
:class:`~texsmith.diagnostics.DiagnosticSink` and renders them its own way:
the CLI prints ``file:line:col: severity code: message``, the logging emitter
forwards the same line to :mod:`logging`. The legacy ``warning()``/``error()``
calls build a record with the free-form ``texsmith`` code and no location, so
engine and network messages share the collector with the passes.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Protocol, runtime_checkable

from texsmith.diagnostics import (
    LEGACY_CODE,
    NO_SPAN,
    Diagnostic,
    DiagnosticSink,
    FileTable,
    Severity,
    format_diagnostic,
)

from .exceptions import ConversionError


logger = logging.getLogger(__name__)


@runtime_checkable
class DiagnosticEmitter(Protocol):
    """Interface used to surface warnings, errors, and structured events."""

    debug_enabled: bool

    def warning(self, message: str, exc: BaseException | None = None) -> None: ...

    def error(self, message: str, exc: BaseException | None = None) -> None: ...

    def event(self, name: str, payload: Mapping[str, Any]) -> None: ...

    def diagnostic(self, diagnostic: Diagnostic, cause: BaseException | None = None) -> None: ...


class NullEmitter:
    """Emitter that ignores every diagnostic."""

    debug_enabled: bool = False

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        return

    def error(self, message: str, exc: BaseException | None = None) -> None:
        return

    def event(self, name: str, payload: Mapping[str, Any]) -> None:
        return

    def diagnostic(self, diagnostic: Diagnostic, cause: BaseException | None = None) -> None:
        return


class SinkEmitter:
    """Base of the emitters that collect: owns the sink, renders each new record.

    Subclasses implement :meth:`render` (and :meth:`event`). ``warning()`` and
    ``error()`` are the legacy entry points: a record with the ``texsmith``
    code and no location, the exception kept as rendering context only. They
    go through :meth:`diagnostic` like every other record, so a subclass that
    filters there (the render command's ``--deprecated`` level) sees the whole
    stream and not only the coded half.
    """

    debug_enabled: bool

    def __init__(self, *, debug_enabled: bool = False, files: FileTable | None = None) -> None:
        self.debug_enabled = debug_enabled
        self.sink = DiagnosticSink(files, on_emit=self.render)

    @property
    def files(self) -> FileTable:
        return self.sink.files

    def diagnostic(self, diagnostic: Diagnostic, cause: BaseException | None = None) -> None:
        self.sink.add(diagnostic, cause=cause)

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        self.diagnostic(legacy_diagnostic(Severity.WARNING, message), exc)

    def error(self, message: str, exc: BaseException | None = None) -> None:
        self.diagnostic(legacy_diagnostic(Severity.ERROR, message), exc)

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
    "debug_enabled",
    "ensure_emitter",
    "format_event_message",
    "legacy_diagnostic",
    "raise_conversion_error",
    "record_event",
]


def ensure_emitter(emitter: DiagnosticEmitter | None) -> DiagnosticEmitter:
    """Return a usable emitter, defaulting to the null implementation."""
    return emitter if emitter is not None else NullEmitter()


def debug_enabled(emitter: DiagnosticEmitter | None) -> bool:
    """Return whether debug mode is active for the given emitter."""
    return bool(emitter and getattr(emitter, "debug_enabled", False))


def record_event(
    emitter: DiagnosticEmitter | None,
    event: str,
    payload: Mapping[str, Any],
) -> None:
    """Forward a structured diagnostic event."""
    ensure_emitter(emitter).event(event, payload)


def raise_conversion_error(
    emitter: DiagnosticEmitter | None,
    message: str,
    exc: Exception,
) -> None:
    """Emit an error diagnostic before raising a conversion failure."""
    ensure_emitter(emitter).error(message, exc)
    error = ConversionError(message)
    error._texsmith_logged = True  # noqa: SLF001
    raise error from exc
