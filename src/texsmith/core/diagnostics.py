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
        try:
            self._logger.debug("diagnostic event %s: %s", name, dict(payload))
        except Exception:  # pragma: no cover - defensive
            self._logger.debug("failed to log diagnostic event %s", name, exc_info=True)


__all__ = [
    "DiagnosticEmitter",
    "LoggingEmitter",
    "NullEmitter",
]
