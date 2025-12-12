"""CLI helpers for inspecting and scaffolding LaTeX templates."""

from __future__ import annotations

from collections.abc import Iterable
from importlib import metadata
from pathlib import Path
import shutil

import typer

from texsmith.core.fragments import FRAGMENT_REGISTRY, TemplateError
from texsmith.core.templates import TemplateError as TemplateTplError, load_template
from texsmith.core.templates.builtins import iter_builtin_templates
from texsmith.core.templates.loader import _iter_local_candidates, _looks_like_template_root

from ..state import emit_error, ensure_rich_compat, get_cli_state


def _format_list(values: Iterable[str]) -> str:
    """Format a sequence of strings into a comma-separated list or a placeholder.

    This ensures consistent pretty-printing for user display, handling empty
    sequences gracefully by returning a standard placeholder.
    """
    sequence = list(values)
    return ", ".join(sequence) if sequence else "-"


def _discover_local_templates(base: Path | None = None) -> list[Path]:
    """Scan the working directory for potential template candidates.

    This enables users to use project-local templates without needing to install
    them as Python packages, supporting rapid development and customization.
    """
    base_path = (base or Path.cwd()).resolve()
    roots = {base_path, base_path / "templates"}
    candidates: list[Path] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_dir() and _looks_like_template_root(child):
                candidates.append(child)
    return sorted({candidate.resolve() for candidate in candidates})


def list_templates() -> None:
    """Print a table listing built-in, entry-point, and local templates."""

    ensure_rich_compat()
    try:
        from rich import box
        from rich.table import Table
    except ImportError:  # pragma: no cover - fallback when Rich is unavailable
        _print_template_list_plain()
        return

    console = get_cli_state().console
    table = Table(
        title="Available Templates",
        box=box.SQUARE,
        show_edge=True,
        header_style="bold cyan",
    )
    table.add_column("Name", style="magenta")
    table.add_column("Origin", style="green")
    table.add_column("Location")

    entries = _collect_template_entries()
    if not entries:
        table.add_row("-", "-", "No templates found")
    else:
        for entry in entries:
            table.add_row(entry["name"], entry["origin"], entry["root"])

    console.print(table)


def _print_template_list_plain() -> None:
    typer.echo("Available templates:")
    entries = _collect_template_entries()
    if not entries:
        typer.echo("  - (none)")
        return
    for entry in entries:
        typer.echo(f"  - {entry['name']} ({entry['origin']}) -> {entry['root']}")


def _collect_template_entries() -> list[dict[str, str]]:
    """Aggregate available templates from built-ins, entry points, and local paths.

    This unifies multiple template sources into a single list, giving the user
    a complete view of all available templates regardless of how they are installed.
    """
    entries: list[dict[str, str]] = []

    for slug in iter_builtin_templates():
        try:
            template = load_template(slug)
        except TemplateError:
            continue
        entries.append({"name": slug, "origin": "builtin", "root": str(template.root)})

    try:
        entry_points = metadata.entry_points().select(group="texsmith.templates")
    except Exception:  # pragma: no cover - extremely defensive
        entry_points = ()

    for entry_point in entry_points:
        try:
            template = load_template(entry_point.name)
        except TemplateError:
            continue
        entries.append(
            {"name": entry_point.name, "origin": "entry-point", "root": str(template.root)}
        )

    for local_root in _discover_local_templates():
        entries.append({"name": local_root.name, "origin": "local", "root": str(local_root)})

    seen: set[tuple[str, str]] = set()
    unique_entries: list[dict[str, str]] = []
    for entry in entries:
        key = (entry["name"], entry["root"])
        if key in seen:
            continue
        seen.add(key)
        unique_entries.append(entry)
    return sorted(unique_entries, key=lambda item: (item["origin"], item["name"]))


def _discover_local_templates(base: Path | None = None) -> list[Path]:
    """Scan for potential template roots under cwd/parents and templates/."""
    base_path = (base or Path.cwd()).resolve()
    roots = {base_path, base_path / "templates"}
    candidates: list[Path] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_dir() and _looks_like_template_root(child):
                candidates.append(child)

    # Also walk ancestor templates folders via loader helper.
    for candidate in _iter_local_candidates(""):
        if candidate.is_dir() and _looks_like_template_root(candidate):
            candidates.append(candidate)
    return sorted({candidate.resolve() for candidate in candidates})


def show_template_info(identifier: str) -> None:
    """Display metadata extracted from a LaTeX template manifest."""

    ensure_rich_compat()
    try:
        from rich import box as rich_box
        from rich.panel import Panel as RichPanel
        from rich.pretty import Pretty as RichPretty
        from rich.table import Table as RichTable
    except ImportError:  # pragma: no cover - fallback when Rich is stubbed
        rich_box = RichPanel = RichPretty = RichTable = None  # type: ignore[assignment]  # noqa: N806

    try:
        template = load_template(identifier)
    except TemplateTplError as exc:
        emit_error(f"Unable to load template '{identifier}': {exc}", exception=exc)
        raise typer.Exit(code=1) from exc

    info = template.info
    console = get_cli_state().console

    if RichTable is None or RichPanel is None or RichPretty is None or rich_box is None:
        typer.echo(f"Template: {identifier}")
        typer.echo(f"Name: {info.name}")
        typer.echo(f"Version: {info.version}")
        if getattr(info, "description", None):
            typer.echo(f"Description: {info.description}")
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
                desc = getattr(value, "description", None) or "-"
                typer.echo(
                    f"  - {key}: type={value.type or 'any'}, format={value.format or '-'}, "
                    f"default={value.default!r}, desc={desc}"
                )

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

        fragment_entries = getattr(info, "fragments", None) or []
        typer.echo("Fragments:")
        if fragment_entries:
            for fragment_name in fragment_entries:
                try:
                    definition = FRAGMENT_REGISTRY.resolve(fragment_name)
                    desc = definition.description or ""
                    attrs = ", ".join(sorted(definition.attributes.keys())) or "-"
                    typer.echo(f"  - {fragment_name}: {desc} (attributes: {attrs})")
                except Exception:
                    typer.echo(f"  - {fragment_name}")
        else:
            typer.echo("  - None")

        slots, default_slot = info.resolve_slots()
        typer.echo("Slots:")
        for name, slot in sorted(slots.items()):
            base = slot.base_level if slot.base_level is not None else "-"
            depth = slot.depth or "-"
            effective = slot.resolve_level(0)
            desc = getattr(slot, "description", None)
            typer.echo(
                f"  - {name} ({'default' if name == default_slot else 'optional'}): "
                f"base={base}, depth={depth}, offset={slot.offset}, "
                f"effective={effective}, strip_heading={'yes' if slot.strip_heading else 'no'}"
                + (f" — {desc}" if desc else "")
            )
        return

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
            box=rich_box.SQUARE,
            header_style="bold cyan",
            show_edge=True,
            show_lines=True,
        )
        attrs.add_column("Key", style="magenta")
        attrs.add_column("Type", style="green")
        attrs.add_column("Format", style="green")
        attrs.add_column("Default")
        attrs.add_column("Description")
        for key, value in sorted(info.attributes.items()):
            attrs.add_row(
                key,
                str(getattr(value, "type", None) or "any"),
                str(getattr(value, "format", None) or "-"),
                RichPretty(getattr(value, "default", None), indent_guides=True),
                getattr(value, "description", None) or "-",
            )
        console.print(attrs)

    assets = list(template.iter_assets())
    assets_table = RichTable(
        title="Assets",
        box=rich_box.SQUARE,
        header_style="bold cyan",
        show_edge=True,
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

    fragment_entries = info.fragments or []
    fragments_table = RichTable(
        title="Fragments",
        box=rich_box.SQUARE,
        header_style="bold cyan",
        show_edge=True,
    )
    fragments_table.add_column("Name", style="magenta")
    fragments_table.add_column("Description")
    fragments_table.add_column("Attributes")
    if fragment_entries:
        for fragment_name in fragment_entries:
            try:
                definition = FRAGMENT_REGISTRY.resolve(fragment_name)
                desc = definition.description or "-"
                attrs = ", ".join(sorted(definition.attributes.keys())) or "-"
                fragments_table.add_row(fragment_name, desc, attrs)
            except Exception:
                fragments_table.add_row(fragment_name, "-", "-")
    else:
        fragments_table.add_row("-", "None", "-")
    console.print(fragments_table)

    slots, default_slot = info.resolve_slots()
    slots_table = RichTable(
        title="Slots",
        box=rich_box.SQUARE,
        header_style="bold cyan",
        show_edge=True,
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


def scaffold_template(identifier: str, destination: Path) -> None:
    """Copy the selected template into ``destination`` for customization."""

    try:
        template = load_template(identifier)
    except TemplateError as exc:
        emit_error(f"Unable to load template '{identifier}': {exc}", exception=exc)
        raise typer.Exit(code=1) from exc

    destination = destination.expanduser().resolve()
    try:
        shutil.copytree(template.root, destination, dirs_exist_ok=True)
    except OSError as exc:
        emit_error(f"Failed to scaffold template into '{destination}': {exc}", exception=exc)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Scaffolded template '{identifier}' into {destination}")


__all__ = [
    "list_templates",
    "scaffold_template",
    "show_template_info",
]
