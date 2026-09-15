"""Typer application wiring for the TeXSmith CLI."""

from __future__ import annotations

import click
import typer
from typer.core import TyperCommand, TyperGroup

from texsmith.ui.cli.commands.render import render
from texsmith.ui.cli.commands.site import app as site_app

from .state import debug_enabled, emit_error


#: The command every argument that names no group belongs to.
ROOT_COMMAND = "render"


class RootContext(click.Context):
    """The context of a command invoked under its parent's name.

    :class:`RootGroup` leaves the root command unnamed, so Click builds its
    command path as the group's name followed by nothing; the usage line and
    every ``Try '… --help'`` read better without the gap that leaves.
    """

    @property
    def command_path(self) -> str:
        """The parent's path, with no room left for the name this command has not got."""
        return super().command_path.strip()


class HelpOnEmptyCommand(TyperCommand):
    """Typer command that disables positional argument enforcement."""

    context_class = RootContext

    def __init__(self, *args: object, **kwargs: object) -> None:  # type: ignore[override]
        super().__init__(*args, **kwargs)
        for param in self.params:
            if isinstance(param, click.Argument):
                param.required = False


class RootGroup(TyperGroup):
    """``texsmith`` is the conversion command, and also the door to the groups.

    ``texsmith doc.md --build`` is the whole CLI as far as most uses go, so
    the root keeps taking a document and its options directly: an argument
    list that does not open with the name of a registered group is the
    :data:`ROOT_COMMAND`'s. That command then answers under the root's own
    name — ``texsmith --help`` describes the conversion, and names the groups
    in its epilog, rather than describing a chooser.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Hand the arguments to the root command unless a group is named."""
        if not args or args[0] not in self.commands:
            args = [ROOT_COMMAND, *args]
        return super().parse_args(ctx, args)

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        """Resolve as Click does, but leave the root command unnamed."""
        name, command, rest = super().resolve_command(ctx, args)
        return (None if name == ROOT_COMMAND else name), command, rest


app = typer.Typer(
    help="Convert Markdown into LaTeX, Typst or PDF.",
    context_settings={"help_option_names": ["--help"]},
    cls=RootGroup,
)


app.command(
    ROOT_COMMAND,
    cls=HelpOnEmptyCommand,
    epilog="Command groups: 'texsmith site --help' prepares a documentation site.",
)(render)
app.add_typer(site_app, name="site")


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
