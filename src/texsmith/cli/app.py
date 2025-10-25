"""Typer application wiring for the TeXSmith CLI."""

from __future__ import annotations

from pathlib import Path

from rich.traceback import Traceback
import typer

from ..bibliography import BibliographyCollection
from ..markdown import DEFAULT_MARKDOWN_EXTENSIONS
from .bibliography import print_bibliography_overview
from .commands.build import build
from .commands.convert import convert
from .state import debug_enabled, emit_error, get_cli_state, set_cli_state


app = typer.Typer(
    help="Convert MkDocs HTML fragments into LaTeX.",
    context_settings={"help_option_names": ["--help"]},
    invoke_without_command=True,
)

bibliography_app = typer.Typer(
    help="Inspect and interact with BibTeX bibliography files.",
    context_settings={"help_option_names": ["--help"]},
)

app.add_typer(bibliography_app, name="bibliography")


@app.callback()
def _app_root(
    ctx: typer.Context,
    list_extensions: bool = typer.Option(
        False,
        "--list-extensions",
        help="List Markdown extensions enabled by default and exit.",
    ),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help=("Increase CLI verbosity. Combine multiple times for additional diagnostics."),
    ),
    debug: bool = typer.Option(
        False,
        "--debug/--no-debug",
        help="Show full tracebacks when an unexpected error occurs.",
    ),
) -> None:
    ctx.obj = get_cli_state()
    set_cli_state(verbosity=verbose, debug=debug)

    if list_extensions:
        for extension in DEFAULT_MARKDOWN_EXTENSIONS:
            typer.echo(extension)
        raise typer.Exit(code=0)


@bibliography_app.command(name="list")
def bibliography_list(
    bib_files: list[Path] = typer.Argument(
        ...,
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
    collection = BibliographyCollection()
    collection.load_files(bib_files)
    print_bibliography_overview(collection)


app.command(name="convert")(convert)
app.command(name="build")(build)


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
