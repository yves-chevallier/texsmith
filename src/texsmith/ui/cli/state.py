"""Shared CLI state management utilities."""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
import sys
from typing import TYPE_CHECKING, Any, cast

import click
import typer


if TYPE_CHECKING:
    from rich.console import Console

__all__ = [
    "CLIState",
    "debug_enabled",
    "emit_error",
    "emit_warning",
    "ensure_rich_compat",
    "get_cli_state",
    "render_message",
    "set_cli_state",
]


def ensure_rich_compat() -> None:
    """Patch Rich stub modules provided by tests to expose required attributes."""
    import importlib.machinery
    import sys as _sys
    import types

    rich_mod = _sys.modules.get("rich")
    if rich_mod is None:
        return
    if getattr(rich_mod, "__spec__", None) is None:
        rich_mod.__spec__ = importlib.machinery.ModuleSpec("rich", loader=None)

    is_stub = getattr(rich_mod, "__file__", None) is None

    if is_stub:
        try:
            import typer.core as typer_core

            cast(Any, typer_core).HAS_RICH = False
        except ImportError:  # pragma: no cover - typer not available
            pass
        try:
            import typer.main as typer_main

            cast(Any, typer_main).HAS_RICH = False
        except ImportError:  # pragma: no cover - typer not available
            pass

    if not hasattr(rich_mod, "box"):
        box_module = types.ModuleType("rich.box")
        cast(Any, box_module).SQUARE = object()
        cast(Any, box_module).MINIMAL_DOUBLE_HEAD = object()
        cast(Any, box_module).SIMPLE = object()
        cast(Any, rich_mod).box = box_module
        _sys.modules.setdefault("rich.box", box_module)


@dataclass(slots=True)
class CLIState:
    """Shared state controlling CLI diagnostics."""

    verbosity: int = 0
    show_tracebacks: bool = False
    events: dict[str, list[dict[str, Any]]] = field(default_factory=dict, init=False)
    _console: Console | None = field(default=None, init=False, repr=False)
    _err_console: Console | None = field(default=None, init=False, repr=False)

    @property
    def console(self) -> Console:
        """Return a lazily instantiated stdout console."""
        from rich.console import Console

        current = getattr(self._console, "file", None)
        if self._console is None or current is not sys.stdout:
            try:
                self._console = Console(file=sys.stdout)
            except TypeError:  # pragma: no cover - stub Console fallback
                self._console = Console()
        return self._console

    @property
    def err_console(self) -> Console:
        """Return a lazily instantiated stderr console."""
        from rich.console import Console

        current = getattr(self._err_console, "file", None)
        if self._err_console is None or current is not sys.stderr:
            try:
                self._err_console = Console(file=sys.stderr, highlight=False)
            except TypeError:  # pragma: no cover - stub Console fallback
                self._err_console = Console()
        return self._err_console

    def record_event(self, name: str, payload: Mapping[str, Any] | None = None) -> None:
        """Store a structured diagnostic event for later presentation."""
        entry = dict(payload or {})
        self.events.setdefault(name, []).append(entry)

    def consume_events(self, name: str) -> list[dict[str, Any]]:
        """Retrieve and clear events for the given name."""
        return self.events.pop(name, [])


_STATE_VAR: ContextVar[CLIState | None] = ContextVar("texsmith_cli_state", default=None)


def get_cli_state(
    ctx: typer.Context | click.Context | None = None,
    *,
    create: bool = True,
) -> CLIState:
    """Return the CLI state associated with the active Typer context."""
    if ctx is None:
        try:
            candidate = click.get_current_context(silent=True)
        except RuntimeError:
            candidate = None
        if isinstance(candidate, typer.Context):
            ctx = candidate

    state: CLIState | None = None

    if isinstance(ctx, typer.Context):
        current_ctx: typer.Context | None = ctx
        while current_ctx is not None:
            obj = getattr(current_ctx, "obj", None)
            if isinstance(obj, CLIState):
                state = obj
                break
            current_ctx = getattr(current_ctx, "parent", None)
        if state is None and create:
            state = CLIState()
            current_ctx = ctx
            current_ctx.obj = state
        if state is not None:
            _STATE_VAR.set(state)

    if state is None:
        fallback = _STATE_VAR.get(None)
        if fallback is None:
            if not create:
                raise RuntimeError("CLI state is not initialised for this context.")
            fallback = CLIState()
            _STATE_VAR.set(fallback)
        state = fallback

    return state


def set_cli_state(
    *,
    ctx: typer.Context | None = None,
    verbosity: int | None = None,
    debug: bool | None = None,
) -> CLIState:
    """Update the CLI state, returning the current instance."""
    state = get_cli_state(ctx)
    if verbosity is not None:
        state.verbosity = max(0, verbosity)
    if debug is not None:
        state.show_tracebacks = debug
    return state


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

    if level == "info":
        # Use a neutral console log for info to align with pipeline logging.
        console = state.console
        if getattr(console, "log", None):
            console.log(message)
        return

    from rich.text import Text

    style = "red" if level == "error" else "yellow"
    label_style = f"bold {style}"
    if hasattr(Text, "assemble"):
        text = Text.assemble((f"{level}: ", label_style), (message, style))
    else:  # pragma: no cover - stub Text fallback
        text = Text()
        text.append(f"{level}: ")
        text.append(message)
    extra_lines: list[str] = []
    if exception is not None and state.verbosity >= 1:
        detail = str(exception).strip()
        if detail and detail not in message:
            extra_lines.append(detail)
        extra_lines.append(f"type: {type(exception).__name__}")
        notes = getattr(exception, "__notes__", None)
        if notes:
            extra_lines.extend(str(note) for note in notes)
        if state.verbosity >= 2:
            chain = _exception_chain(exception)
            if chain:
                extra_lines.append("caused by:")
                extra_lines.extend(f"  {entry}" for entry in chain)
        if state.verbosity >= 3:
            extra_lines.append(f"repr: {exception!r}")

    if extra_lines:
        if hasattr(text, "append"):
            text.append("\n")
            if hasattr(Text, "assemble"):
                text.append("\n".join(extra_lines), style=style)
            else:  # pragma: no cover - stub Text fallback
                text.append("\n".join(extra_lines))
        else:  # pragma: no cover - fallback if text is a plain string
            text = f"{text}\n" + "\n".join(extra_lines)

    console = state.err_console if level != "info" else state.console
    if type(console).__name__.startswith("_Stub"):  # pragma: no cover - stub Console fallback
        target = sys.stderr if level != "info" else sys.stdout
        print(text if isinstance(text, str) else str(text), file=target)
    else:
        console.print(text)


def emit_warning(message: str, *, exception: BaseException | None = None) -> None:
    """Log a warning-level message to stderr respecting verbosity settings."""
    render_message("warning", message, exception=exception)


def emit_error(message: str, *, exception: BaseException | None = None) -> None:
    """Log an error-level message to stderr respecting verbosity settings."""
    if exception is not None and getattr(exception, "_texsmith_logged", False):
        return
    render_message("error", message, exception=exception)


def debug_enabled() -> bool:
    """Return whether full tracebacks should be displayed."""
    try:
        return get_cli_state(create=False).show_tracebacks
    except RuntimeError:
        return False
