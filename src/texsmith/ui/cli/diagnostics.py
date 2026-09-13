"""Diagnostic emitter bridging the core pipeline with CLI rendering utilities."""

from __future__ import annotations

from collections.abc import Mapping
import sys
from typing import Any

from texsmith.diagnostics import (
    Diagnostic,
    FileTable,
    Severity,
    SinkEmitter,
    format_diagnostic,
    format_event_message,
)

from .state import CLIState, exception_details, get_cli_state, render_message


#: Rich styles per severity; Rich drops them when stderr is not a terminal.
SEVERITY_STYLES: dict[Severity, str] = {
    Severity.HINT: "dim",
    Severity.INFO: "cyan",
    Severity.WARNING: "yellow",
    Severity.ERROR: "red",
}


class CliEmitter(SinkEmitter):
    """Collect diagnostics and print each new one as ``file:line:col: severity code: message``."""

    def __init__(
        self,
        state: CLIState | None = None,
        *,
        debug_enabled: bool | None = None,
        files: FileTable | None = None,
    ) -> None:
        self._state = state or get_cli_state()
        if debug_enabled is None:
            debug_enabled = self._state.show_tracebacks
        super().__init__(debug_enabled=bool(debug_enabled), files=files)

    def render(self, diagnostic: Diagnostic, cause: BaseException | None) -> None:
        state = self._state
        if state.quiet and diagnostic.severity < Severity.WARNING:
            return
        body = format_diagnostic(diagnostic, self.files, verbosity=state.verbosity)
        details = exception_details(cause, diagnostic.message, verbosity=state.verbosity)
        if details:
            body = "\n".join([body, *(f"  {line}" for line in details)])
        _print_to_stderr(state, body, SEVERITY_STYLES[diagnostic.severity])

    def event(self, name: str, payload: Mapping[str, Any]) -> None:
        data = dict(payload)
        self._state.record_event(name, data)
        message = format_event_message(name, data)
        if message:
            render_message("info", message)


def _print_to_stderr(state: CLIState, body: str, style: str) -> None:
    console = state.err_console
    if type(console).__name__.startswith("_Stub"):  # pragma: no cover - stub Console fallback
        sys.stderr.write(body + "\n")
        return
    from rich.text import Text

    # Never wrapped: editors and CI parse ``file:line:col:`` at the head of the line.
    console.print(Text(body, style=style), soft_wrap=True)


__all__ = ["SEVERITY_STYLES", "CliEmitter"]
