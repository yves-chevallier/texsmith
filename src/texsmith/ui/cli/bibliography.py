"""Bibliography-related CLI helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer

from texsmith.core.bibliography import BibliographyCollection

from .state import ensure_rich_compat, get_cli_state


if TYPE_CHECKING:
    from rich.panel import Panel


def _iterable_items(value: object) -> Iterable[object]:
    """Normalize a value into an iterable, treating strings as scalars.

    This helper ensures consistent processing of bibliography fields, which may be
    single values (strings) or lists of values, by wrapping single items in a tuple.
    """
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return value
    return ()


def format_bibliography_person(person: Mapping[str, object]) -> str:
    """Render a bibliography person dictionary into a readable string."""
    parts: list[str] = []
    for field in ("first", "middle", "prelast", "last", "lineage"):
        value = person.get(field)
        if isinstance(value, str):
            text = value.strip()
            if text:
                parts.append(text)
            continue
        for segment in _iterable_items(value):
            if segment:
                parts.append(str(segment))

    text = " ".join(part for part in parts if part)
    if text:
        return text
    fallback = person.get("text")
    return str(fallback).strip() if isinstance(fallback, str) else ""


def format_person_list(persons: Iterable[Mapping[str, object]]) -> str:
    """Join a sequence of person dictionaries into a comma-separated string."""
    names = [format_bibliography_person(person) for person in persons]
    return ", ".join(name for name in names if name)


def build_reference_panel(reference: Mapping[str, object]) -> Panel:
    """Create a Rich panel that visualises a single bibliography entry."""
    from rich import box
    from rich.panel import Panel
    from rich.table import Table

    raw_fields = reference.get("fields")
    fields: dict[str, Any]
    if isinstance(raw_fields, Mapping):
        fields = {str(key): value for key, value in raw_fields.items()}
    else:
        fields = {}
    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold green", no_wrap=True)
    grid.add_column()

    def _pop_field(*keys: str) -> str | None:
        for key in keys:
            value = fields.pop(key, None)
            if isinstance(value, bytes):
                text = value.decode("utf-8", errors="ignore").strip()
                if text:
                    return text
            elif isinstance(value, str):
                text = value.strip()
                if text:
                    return text
            elif value is not None:
                return str(value)
        return None

    def _add_field(label: str, value: object) -> None:
        if value is None:
            return
        if isinstance(value, str) and not value.strip():
            return
        grid.add_row(label, str(value))

    title = _pop_field("title")
    _add_field("Title", title)

    year = _pop_field("year")
    _add_field("Year", year)

    journal = _pop_field("journal", "booktitle")
    _add_field("Journal", journal)

    persons_block = reference.get("persons")
    if isinstance(persons_block, Mapping):
        authors = persons_block.get("author")
        if isinstance(authors, Iterable):
            cast_authors = cast(Sequence[Mapping[str, object]], tuple(authors))
            _add_field("Authors", format_person_list(cast_authors))

    sources = [
        str(Path(str(path))) for path in _iterable_items(reference.get("source_files")) if path
    ]
    if sources:
        formatted_sources = ", ".join(sources)
        _add_field("Sources", formatted_sources)

    for key, value in sorted(fields.items()):
        _add_field(key.title(), value)

    key = str(reference.get("key", "Reference"))
    entry_type = str(reference.get("type", "reference"))
    title = f"{key} ({entry_type})"
    return Panel(grid, title=title, box=box.SIMPLE)


def print_bibliography_overview(collection: BibliographyCollection) -> None:
    """Render a formatted summary of bibliography files, issues, and entries."""
    ensure_rich_compat()
    try:
        from rich import box
        from rich.panel import Panel
        from rich.table import Table
    except ImportError:  # pragma: no cover - fallback when Rich is unavailable
        _print_bibliography_plain(collection)
        return

    console = get_cli_state().console

    stats = collection.file_stats
    if stats:
        stats_table = Table(
            title="Bibliography Files",
            box=box.SIMPLE,
            show_edge=True,
            header_style="bold cyan",
        )
        stats_table.add_column("File", overflow="fold")
        stats_table.add_column("Entries", justify="right")
        for file_path, entry_count in stats:
            stats_table.add_row(str(file_path), str(entry_count))
        console.print(stats_table)

    if collection.issues:
        issue_table = Table(
            title="Warnings",
            box=box.SIMPLE,
            header_style="bold yellow",
            show_edge=True,
        )
        issue_table.add_column("Key", style="yellow", no_wrap=True)
        issue_table.add_column("Message", style="yellow")
        issue_table.add_column("Sources", style="yellow")
        for issue in collection.issues:
            issue_table.add_row(
                issue.key or "—",
                issue.message,
                str(issue.source) if issue.source else "—",
            )
        console.print(issue_table)

    references = collection.list_references()
    if not references:
        console.print("[dim]No references found.[/]")
        return

    for reference in references:
        panel = build_reference_panel(reference)
        console.print(panel)
        console.print()


def _print_bibliography_plain(collection: BibliographyCollection) -> None:
    """Simple text fallback when Rich is not available."""
    typer.echo("Bibliography Files:")
    stats = collection.file_stats
    if stats:
        for file_path, entry_count in stats:
            typer.echo(f"  - {file_path} ({entry_count} entries)")
    else:
        typer.echo("  - (none)")

    if collection.issues:
        typer.echo("Warnings:")
        for issue in collection.issues:
            key = issue.key or "-"
            source = str(issue.source) if issue.source else "-"
            typer.echo(f"  - [{key}] {issue.message} (source: {source})")

    references = collection.list_references()
    if not references:
        typer.echo("No references found.")
        return

    typer.echo("Entries:")
    typer.echo("References:")
    for reference in references:
        key = reference.get("key", "Reference")
        entry_type = reference.get("type", "reference")
        typer.echo(f"- {key} ({entry_type})")
        persons_block = reference.get("persons")
        if isinstance(persons_block, Mapping):
            authors = persons_block.get("author")
            if isinstance(authors, Iterable):
                cast_authors = cast(Sequence[Mapping[str, object]], tuple(authors))
                typer.echo(f"    Authors: {format_person_list(cast_authors)}")
        fields = reference.get("fields")
        if isinstance(fields, Mapping):
            for field_key, field_value in sorted(fields.items()):
                typer.echo(f"    {field_key.title()}: {field_value}")
        sources = reference.get("source_files")
        entries = [str(Path(str(path))) for path in _iterable_items(sources) if path]
        if entries:
            typer.echo(f"    Sources: {', '.join(entries)}")
        typer.echo()
