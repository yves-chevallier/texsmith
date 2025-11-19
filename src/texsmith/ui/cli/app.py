"""Typer application wiring for the TeXSmith CLI."""

from __future__ import annotations

import sys
from typing import Any

import click
import typer
from typer.core import TyperCommand

from texsmith.ui.cli.commands.render import render
from texsmith.ui.cli.commands.templates import list_templates

from ._options import DIAGNOSTICS_PANEL
from .state import debug_enabled, emit_error, ensure_rich_compat, get_cli_state, set_cli_state


class HelpOnEmptyCommand(TyperCommand):
    """Typer command that disables positional argument enforcement."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        super().__init__(*args, **kwargs)
        for param in self.params:
            if isinstance(param, click.Argument):
                param.required = False


app = typer.Typer(
    help="Convert MkDocs HTML fragments into LaTeX.",
    context_settings={"help_option_names": ["--help"]},
    invoke_without_command=True,
)


@app.callback()
def _app_root(
    ctx: typer.Context,
    list_extensions: bool = typer.Option(
        False,
        "--list-extensions",
        help="List Markdown extensions enabled by default and exit.",
        rich_help_panel=DIAGNOSTICS_PANEL,
    ),
    list_templates_flag: bool = typer.Option(
        False,
        "--list-templates",
        help="List available templates (builtin, entry-point, and local) and exit.",
        rich_help_panel=DIAGNOSTICS_PANEL,
    ),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help=("Increase CLI verbosity. Combine multiple times for additional diagnostics."),
        rich_help_panel=DIAGNOSTICS_PANEL,
    ),
    debug: bool = typer.Option(
        False,
        "--debug/--no-debug",
        help="Show full tracebacks when an unexpected error occurs.",
        rich_help_panel=DIAGNOSTICS_PANEL,
    ),
) -> None:
    state = set_cli_state(ctx=ctx, verbosity=verbose, debug=debug)
    ctx.obj = state

    if list_extensions:
        from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS

        for extension in DEFAULT_MARKDOWN_EXTENSIONS:
            typer.echo(extension)
        raise typer.Exit(code=0)

    if list_templates_flag:
        list_templates()
        raise typer.Exit(code=0)

    if ctx.resilient_parsing:
        return


app.command(name="render", cls=HelpOnEmptyCommand)(render)


def main() -> None:
    """Entry point compatible with console scripts."""
    original_argv = sys.argv[:]
    patched = False
    commands = {"render"}
    if len(sys.argv) > 1:
        first = sys.argv[1]
        if not first.startswith("-") and first not in commands:
            sys.argv = [sys.argv[0], "render", *sys.argv[1:]]
            patched = True
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
    finally:
        if patched:
            sys.argv = original_argv


__all__ = ["app", "main"]
