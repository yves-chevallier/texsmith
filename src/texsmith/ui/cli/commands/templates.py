"""CLI helpers for inspecting LaTeX templates."""

from __future__ import annotations

from collections.abc import Iterable

import click
import typer
from typer.models import ArgumentInfo

from ..state import emit_error, ensure_rich_compat, get_cli_state


def _format_list(values: Iterable[str]) -> str:
    sequence = list(values)
    return ", ".join(sequence) if sequence else "-"


def template_info(
    identifier: str | None = typer.Argument(None, help="Template name or path to inspect."),
) -> None:
    """Display metadata extracted from a LaTeX template manifest."""
    if identifier is None or isinstance(identifier, ArgumentInfo):
        ctx = click.get_current_context()
        typer.echo(ctx.command.get_help(ctx))
        raise typer.Exit()

    assert isinstance(identifier, str)

    ensure_rich_compat()
    try:
        from rich import box as rich_box
        from rich.panel import Panel as RichPanel
        from rich.pretty import Pretty as RichPretty
        from rich.table import Table as RichTable
    except ImportError:  # pragma: no cover - fallback when Rich is stubbed
        rich_box = RichPanel = RichPretty = RichTable = None  # type: ignore[assignment]  # noqa: N806

    from texsmith.core.templates import TemplateError, load_template

    try:
        template = load_template(identifier)
    except TemplateError as exc:
        emit_error(f"Unable to load template '{identifier}': {exc}", exception=exc)
        raise typer.Exit(code=1) from exc

    info = template.info
    console = get_cli_state().console

    if RichTable is None or RichPanel is None or RichPretty is None or rich_box is None:
        typer.echo(f"Template: {identifier}")
        typer.echo(f"Name: {info.name}")
        typer.echo(f"Version: {info.version}")
        typer.echo(f"Entrypoint: {info.entrypoint}")
        typer.echo(f"Engine: {info.engine or '-'}")
        typer.echo(f"Shell escape: {'yes' if info.shell_escape else 'no'}")
        typer.echo(f"Template root: {template.root}")
        typer.echo(f"TeX Live year: {info.texlive_year or '-'}")
        typer.echo(f"tlmgr packages: {_format_list(info.tlmgr_packages)}")
        typer.echo(f"Formatter overrides: {_format_list(info.override)}")

        if info.attributes:
            typer.echo("Attributes:")
            for key, value in sorted(info.attributes.items()):
                typer.echo(f"  - {key}: {value!r}")

        assets = list(template.iter_assets())
        typer.echo("Assets:")
        if assets:
            for asset in assets:
                try:
                    relative_source = asset.source.relative_to(template.root)
                    source_display = relative_source.as_posix()
                except ValueError:
                    source_display = asset.source.as_posix()
                typer.echo(
                    f"  - {asset.destination.as_posix()} <- {source_display} "
                    f"(templated: {'yes' if asset.template else 'no'}, "
                    f"encoding: {asset.encoding or '-'})"
                )
        else:
            typer.echo("  - No declared assets")

        slots, default_slot = info.resolve_slots()
        typer.echo("Slots:")
        for name, slot in sorted(slots.items()):
            base = slot.base_level if slot.base_level is not None else "-"
            depth = slot.depth or "-"
            effective = slot.resolve_level(0)
            typer.echo(
                f"  - {name} ({'default' if name == default_slot else 'optional'}): "
                f"base={base}, depth={depth}, offset={slot.offset}, "
                f"effective={effective}, strip_heading={'yes' if slot.strip_heading else 'no'}"
            )
        return

    # Rich is available beyond this point.
    assert RichTable is not None
    assert RichPanel is not None
    assert RichPretty is not None
    assert rich_box is not None

    summary = RichTable.grid(padding=(0, 1))
    summary.add_row("Name", info.name)
    summary.add_row("Version", info.version)
    summary.add_row("Entrypoint", info.entrypoint)
    summary.add_row("Engine", info.engine or "-")
    summary.add_row("Shell escape", "yes" if info.shell_escape else "no")
    summary.add_row("Template root", str(template.root))
    summary.add_row("TeX Live year", str(info.texlive_year) if info.texlive_year else "-")
    summary.add_row("tlmgr packages", _format_list(info.tlmgr_packages))
    summary.add_row("Formatter overrides", _format_list(info.override))

    console.print(
        RichPanel(
            summary, box=rich_box.SQUARE, title=f"Template: {identifier}", border_style="cyan"
        )
    )

    if info.attributes:
        attrs = RichTable(
            title="Attributes",
            box=rich_box.MINIMAL_DOUBLE_HEAD,
            header_style="bold cyan",
            show_lines=True,
        )
        attrs.add_column("Key", style="magenta")
        attrs.add_column("Value", style="green")
        for key, value in sorted(info.attributes.items()):
            attrs.add_row(key, RichPretty(value, indent_guides=True))
        console.print(attrs)

    assets = list(template.iter_assets())
    assets_table = RichTable(
        title="Assets",
        box=rich_box.MINIMAL_DOUBLE_HEAD,
        header_style="bold cyan",
    )
    assets_table.add_column("Destination", style="magenta")
    assets_table.add_column("Source", style="green")
    assets_table.add_column("Templated", justify="center")
    assets_table.add_column("Encoding", justify="center")
    if assets:
        for asset in assets:
            try:
                relative_source = asset.source.relative_to(template.root)
                source_display = relative_source.as_posix()
            except ValueError:
                source_display = asset.source.as_posix()
            assets_table.add_row(
                asset.destination.as_posix(),
                source_display,
                "yes" if asset.template else "no",
                asset.encoding or "-",
            )
    else:
        assets_table.add_row("-", "No declared assets", "", "")
    console.print(assets_table)

    slots, default_slot = info.resolve_slots()
    slots_table = RichTable(
        title="Slots",
        box=rich_box.MINIMAL_DOUBLE_HEAD,
        header_style="bold cyan",
    )
    slots_table.add_column("Name", style="magenta")
    slots_table.add_column("Default", justify="center")
    slots_table.add_column("Base Level", justify="right")
    slots_table.add_column("Depth", justify="right")
    slots_table.add_column("Offset", justify="right")
    slots_table.add_column("Effective Level", justify="right")
    slots_table.add_column("Strip Heading", justify="center")

    for name, slot in sorted(slots.items()):
        base = slot.base_level if slot.base_level is not None else "-"
        depth = slot.depth or "-"
        effective = slot.resolve_level(0)
        slots_table.add_row(
            name,
            "*" if name == default_slot else "",
            str(base),
            str(depth),
            str(slot.offset),
            str(effective),
            "yes" if slot.strip_heading else "no",
        )

    console.print(slots_table)


__all__ = ["template_info"]
