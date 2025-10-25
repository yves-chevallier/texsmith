"""Shared CLI state management utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
import sys

from rich.console import Console
from rich.text import Text


@dataclass(slots=True)
class CLIState:
    """Shared state controlling CLI diagnostics."""

    verbosity: int = 0
    show_tracebacks: bool = False
    _console: Console | None = field(default=None, init=False, repr=False)
    _err_console: Console | None = field(default=None, init=False, repr=False)

    @property
    def console(self) -> Console:
        """Return a lazily instantiated stdout console."""
        if self._console is None or self._console.file is not sys.stdout:
            self._console = Console(file=sys.stdout)
        return self._console

    @property
    def err_console(self) -> Console:
        """Return a lazily instantiated stderr console."""
        if self._err_console is None or self._err_console.file is not sys.stderr:
            self._err_console = Console(file=sys.stderr, highlight=False)
        return self._err_console


_CLI_STATE = CLIState()


def get_cli_state() -> CLIState:
    """Return the singleton CLI state shared across commands."""
    return _CLI_STATE


def set_cli_state(*, verbosity: int | None = None, debug: bool | None = None) -> None:
    """Update the global CLI state with verbosity and debug flags."""
    state = get_cli_state()
    if verbosity is not None:
        state.verbosity = max(0, verbosity)
    if debug is not None:
        state.show_tracebacks = debug


def _exception_chain(exc: BaseException) -> list[str]:
    chain: list[str] = []
    visited: set[int] = set()
    current = exc.__cause__ or exc.__context__
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        chain.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__
    return chain


def render_message(
    level: str,
    message: str,
    *,
    exception: BaseException | None = None,
) -> None:
    """Render a formatted message to the console, including optional diagnostics."""
    state = get_cli_state()
    style = "red" if level == "error" else "yellow"
    label_style = f"bold {style}"
    text = Text.assemble(
        (f"{level}: ", label_style),
        (message, style),
    )

    extra_lines: list[str] = []
    if exception is not None and state.verbosity >= 1:
        detail = str(exception).strip()
        if detail and detail not in message:
            extra_lines.append(detail)
        extra_lines.append(f"type: {type(exception).__name__}")
        if exception.__notes__:
            extra_lines.extend(exception.__notes__)
        if state.verbosity >= 2:
            chain = _exception_chain(exception)
            if chain:
                extra_lines.append("caused by:")
                extra_lines.extend(f"  {entry}" for entry in chain)
        if state.verbosity >= 3:
            extra_lines.append(f"repr: {exception!r}")

    if extra_lines:
        text.append("\n")
        text.append("\n".join(extra_lines), style=style)

    console = state.err_console if level != "info" else state.console
    console.print(text)


def emit_warning(message: str, *, exception: BaseException | None = None) -> None:
    """Log a warning-level message to stderr respecting verbosity settings."""
    render_message("warning", message, exception=exception)


def emit_error(message: str, *, exception: BaseException | None = None) -> None:
    """Log an error-level message to stderr respecting verbosity settings."""
    render_message("error", message, exception=exception)


def debug_enabled() -> bool:
    """Return whether full tracebacks should be displayed."""
    return get_cli_state().show_tracebacks
