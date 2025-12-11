"""Diagnostic emitter bridging the core pipeline with CLI rendering utilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from texsmith.core.diagnostics import DiagnosticEmitter, format_event_message

from .state import CLIState, emit_error, emit_warning, get_cli_state, render_message


class CliEmitter(DiagnosticEmitter):
    """Emit diagnostics using the rich-enabled CLI helpers."""

    def __init__(self, state: CLIState | None = None, *, debug_enabled: bool | None = None) -> None:
        self._state = state or get_cli_state()
        if debug_enabled is None:
            debug_enabled = self._state.show_tracebacks
        self.debug_enabled = bool(debug_enabled)

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        emit_warning(message, exception=exc)

    def error(self, message: str, exc: BaseException | None = None) -> None:
        emit_error(message, exception=exc)

    def event(self, name: str, payload: Mapping[str, Any]) -> None:
        data = dict(payload)
        self._state.record_event(name, data)
        message = format_event_message(name, data)
        if message:
            render_message("info", message)


__all__ = ["CliEmitter"]
