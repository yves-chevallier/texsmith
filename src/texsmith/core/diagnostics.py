"""Diagnostic abstractions shared across the conversion pipeline."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Protocol, runtime_checkable


logger = logging.getLogger(__name__)


@runtime_checkable
class DiagnosticEmitter(Protocol):
    """Interface used to surface warnings, errors, and structured events."""

    debug_enabled: bool

    def warning(self, message: str, exc: BaseException | None = None) -> None: ...

    def error(self, message: str, exc: BaseException | None = None) -> None: ...

    def event(self, name: str, payload: Mapping[str, Any]) -> None: ...


class NullEmitter:
    """Emitter that ignores every diagnostic."""

    debug_enabled: bool = False

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        return

    def error(self, message: str, exc: BaseException | None = None) -> None:
        return

    def event(self, name: str, payload: Mapping[str, Any]) -> None:
        return


class LoggingEmitter:
    """Emitter that forwards diagnostics to the standard logging module."""

    def __init__(
        self, *, logger_obj: logging.Logger | None = None, debug_enabled: bool = False
    ) -> None:
        self._logger = logger_obj or logger
        self.debug_enabled = debug_enabled

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        if exc is not None:
            self._logger.warning(message, exc_info=exc)
        else:
            self._logger.warning(message)

    def error(self, message: str, exc: BaseException | None = None) -> None:
        if exc is not None:
            self._logger.error(message, exc_info=exc)
        else:
            self._logger.error(message)

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
    "format_event_message",
]
