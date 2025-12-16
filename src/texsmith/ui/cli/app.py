"""Typer application wiring for the TeXSmith CLI."""

from __future__ import annotations

import click
import typer
from typer.core import TyperCommand

from texsmith.ui.cli.commands.render import render

from .state import debug_enabled, emit_error


class HelpOnEmptyCommand(TyperCommand):
    """Typer command that disables positional argument enforcement."""

    def __init__(self, *args: object, **kwargs: object) -> None:  # type: ignore[override]
        super().__init__(*args, **kwargs)
        for param in self.params:
            if isinstance(param, click.Argument):
                param.required = False


app = typer.Typer(
    help="Convert MkDocs HTML fragments into LaTeX.",
    context_settings={"help_option_names": ["--help"]},
)


app.command(cls=HelpOnEmptyCommand)(render)


def main() -> None:
    """Entry point compatible with console scripts."""
    try:
        app()
    except typer.Exit:
        raise
    except KeyboardInterrupt as exc:
        if debug_enabled():
            raise
        emit_error("Operation cancelled by user.", exception=exc)
        raise typer.Exit(code=1) from exc
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive catch-all
        from .state import get_cli_state

        state = get_cli_state()
        if state.show_tracebacks:
            from rich.traceback import Traceback

            tb = Traceback.from_exception(
                type(exc),
                exc,
                exc.__traceback__,
                show_locals=state.verbosity >= 2,
            )
            state.err_console.print(tb)
        else:
            emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc


__all__ = ["app", "main"]
