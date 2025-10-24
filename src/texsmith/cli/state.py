"""Shared CLI state management utilities."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Console
from rich.text import Text


@dataclass(slots=True)
class CLIState:
    """Shared state controlling CLI diagnostics."""

    verbosity: int = 0
    show_tracebacks: bool = False
    console: Console = field(default_factory=Console)
    err_console: Console = field(default_factory=lambda: Console(stderr=True, highlight=False))


_CLI_STATE = CLIState()


def get_cli_state() -> CLIState:
    return _CLI_STATE


def set_cli_state(*, verbosity: int | None = None, debug: bool | None = None) -> None:
    state = get_cli_state()
    if verbosity is not None:
        state.verbosity = max(0, verbosity)
    if debug is not None:
        state.show_tracebacks = debug


def _exception_chain(exc: Exception) -> list[str]:
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
    exception: Exception | None = None,
) -> None:
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


def emit_warning(message: str, *, exception: Exception | None = None) -> None:
    render_message("warning", message, exception=exception)


def emit_error(message: str, *, exception: Exception | None = None) -> None:
    render_message("error", message, exception=exception)


def debug_enabled() -> bool:
    return get_cli_state().show_tracebacks
