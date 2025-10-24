"""Bibliography-related CLI helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..bibliography import BibliographyCollection


def format_bibliography_person(person: Mapping[str, object]) -> str:
    """Render a bibliography person dictionary into a readable string."""
    parts: list[str] = []
    for field in ("first", "middle", "prelast", "last", "lineage"):
        value = person.get(field)
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            parts.extend(str(segment) for segment in value if segment)
        elif isinstance(value, str) and value.strip():
            parts.append(value.strip())

    text = " ".join(part for part in parts if part)
    if text:
        return text
    fallback = person.get("text")
    return str(fallback).strip() if isinstance(fallback, str) else ""


def format_person_list(persons: Iterable[Mapping[str, object]]) -> str:
    names = [format_bibliography_person(person) for person in persons]
    return ", ".join(name for name in names if name)


def build_reference_panel(reference: Mapping[str, object]) -> Panel:
    fields = dict(reference.get("fields", {}))
    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold green", no_wrap=True)
    grid.add_column()

    def _pop_field(*keys: str) -> str | None:
        for key in keys:
            value = fields.pop(key, None)
            if value:
                return value
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

    authors = reference.get("persons", {}).get("author")
    if isinstance(authors, Iterable):
        _add_field("Authors", format_person_list(authors))

    sources = reference.get("source_files")
    if isinstance(sources, Iterable):
        formatted_sources = ", ".join(str(Path(path)) for path in sources if path)
        _add_field("Sources", formatted_sources)

    for key, value in sorted(fields.items()):
        _add_field(key.title(), value)

    key = str(reference.get("key", "Reference"))
    entry_type = str(reference.get("type", "reference"))
    title = f"{key} ({entry_type})"
    return Panel(grid, title=title, box=box.SIMPLE)


def print_bibliography_overview(collection: BibliographyCollection) -> None:
    console = Console()

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
