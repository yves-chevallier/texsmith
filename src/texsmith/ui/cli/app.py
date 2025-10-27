"""Typer application wiring for the TeXSmith CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import typer
from typer.core import TyperCommand

from texsmith.ui.cli.commands.build import build
from texsmith.ui.cli.commands.convert import convert
from texsmith.ui.cli.commands.templates import template_info

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

bibliography_app = typer.Typer(
    help="Inspect and interact with BibTeX bibliography files.",
    context_settings={"help_option_names": ["--help"]},
    invoke_without_command=True,
)

app.add_typer(bibliography_app, name="bibliography")

latex_app = typer.Typer(
    help="Inspect LaTeX templates and runtime data.",
    context_settings={"help_option_names": ["--help"]},
    invoke_without_command=True,
)
template_app = typer.Typer(
    help="Inspect LaTeX templates available to TeXSmith.",
    context_settings={"help_option_names": ["--help"]},
    invoke_without_command=True,
)

latex_app.add_typer(template_app, name="template")
app.add_typer(latex_app, name="latex")
app.add_typer(template_app, name="template")


@app.callback()
def _app_root(
    ctx: typer.Context,
    list_extensions: bool = typer.Option(
        False,
        "--list-extensions",
        help="List Markdown extensions enabled by default and exit.",
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

    if ctx.resilient_parsing:
        return

    if ctx.invoked_subcommand is None:
        ensure_rich_compat()
        typer.echo(ctx.command.get_help(ctx))
        raise typer.Exit()


@bibliography_app.callback()
def _bibliography_root(ctx: typer.Context) -> None:
    if ctx.resilient_parsing:
        return
    if ctx.invoked_subcommand is None:
        ensure_rich_compat()
        typer.echo(ctx.command.get_help(ctx))
        raise typer.Exit()


@latex_app.callback()
def _latex_root(ctx: typer.Context) -> None:
    if ctx.resilient_parsing:
        return
    if ctx.invoked_subcommand is None:
        ensure_rich_compat()
        typer.echo(ctx.command.get_help(ctx))
        raise typer.Exit()


@template_app.callback()
def _template_root(ctx: typer.Context) -> None:
    if ctx.resilient_parsing:
        return
    if ctx.invoked_subcommand is None:
        ensure_rich_compat()
        typer.echo(ctx.command.get_help(ctx))
        raise typer.Exit()


@bibliography_app.command(name="list", cls=HelpOnEmptyCommand)
def bibliography_list(
    bib_files: list[Path] | None = typer.Argument(
        [],
        metavar="BIBFILE",
        help="One or more BibTeX files to inspect.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
) -> None:
    """Load the given BibTeX files and print a formatted overview table."""
    resolved_files = list(bib_files or [])

    if not resolved_files:
        ctx = click.get_current_context()
        typer.echo(ctx.command.get_help(ctx))
        raise typer.Exit()

    from texsmith.core.bibliography import BibliographyCollection
    from texsmith.ui.cli.bibliography import print_bibliography_overview

    collection = BibliographyCollection()
    collection.load_files(resolved_files)
    print_bibliography_overview(collection)


app.command(name="convert", cls=HelpOnEmptyCommand)(convert)
app.command(name="build", cls=HelpOnEmptyCommand)(build)
template_app.command(name="info", cls=HelpOnEmptyCommand)(template_info)


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


__all__ = ["app", "bibliography_app", "main"]
