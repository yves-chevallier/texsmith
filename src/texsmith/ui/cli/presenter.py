"""Rich-aware presenters for CLI output and diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from texsmith.adapters.latex.log import (
    LatexLogParser,
    LatexMessage,
    LatexMessageSeverity,
)
from texsmith.api.pipeline import ConversionBundle, LaTeXFragment
from texsmith.api.templates import TemplateRenderResult

from .state import CLIState


if TYPE_CHECKING:  # pragma: no cover - typing only
    from rich.console import Console


def _get_console(state: CLIState, *, stderr: bool = False) -> Console | None:
    try:
        console = state.err_console if stderr else state.console
    except Exception:  # pragma: no cover - fallback when Rich unavailable
        return None
    if getattr(console, "is_terminal", False):
        return console
    return None


def _rich_components() -> tuple[Any, Any, Any, Any] | None:
    try:
        from rich import box
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
    except ImportError:  # pragma: no cover - Rich absent
        return None
    return box, Panel, Table, Text


def _format_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(Path.cwd()))
    except ValueError:
        return str(resolved)


def _render_summary(state: CLIState, title: str, rows: Sequence[tuple[str, str, str]]) -> None:
    console = _get_console(state)
    components = _rich_components()
    has_details = any(bool(details) for _, _, details in rows)
    if console is not None and components is not None:
        box_module, _panel_cls, table_cls, _text_cls = components
        table = table_cls(box=box_module.SQUARE, header_style="bold cyan")
        table.title = title
        table.add_column("Artifact", style="cyan")
        table.add_column("Location", style="green")
        if has_details:
            table.add_column("Details", style="magenta")
        for artifact, location, details in rows:
            if has_details:
                table.add_row(artifact, location, details)
            else:
                table.add_row(artifact, location)
        console.print(table)
        return

    # Plain-text fallback
    typer.echo(title)
    for artifact, location, details in rows:
        suffix = f" — {details}" if details else ""
        typer.echo(f"  * {artifact}: {location}{suffix}")


def _detect_assets(directory: Path) -> list[Path]:
    assets_dir = directory / "assets"
    if not assets_dir.is_dir():
        return []
    return sorted(
        (path for path in assets_dir.iterdir() if path.is_file()),
        key=lambda p: p.name.lower(),
    )


def _detect_manifests(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.json") if "manifest" in path.name.lower())


def _detect_debug_html(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.debug.html"))


def present_conversion_summary(
    *,
    state: CLIState,
    output_mode: str,
    bundle: ConversionBundle | None,
    output_path: Path | None,
    render_result: TemplateRenderResult | None,
) -> None:
    rows: list[tuple[str, str, str]] = []

    if render_result is not None:
        main_dir = render_result.main_tex_path.parent
        rows.append(("Main document", _format_path(render_result.main_tex_path), ""))
        for fragment in render_result.fragment_paths:
            rows.append(("Fragment", _format_path(fragment), ""))
        if render_result.bibliography_path is not None:
            rows.append(("Bibliography", _format_path(render_result.bibliography_path), ""))
        for manifest in _detect_manifests(main_dir):
            rows.append(("Manifest", _format_path(manifest), ""))
        for asset in _detect_assets(main_dir):
            rows.append(("Asset", _format_path(asset), ""))
        for debug_html in _detect_debug_html(main_dir):
            rows.append(("Debug HTML", _format_path(debug_html), ""))
        _render_summary(state, "Template Conversion Summary", rows)
        return

    if output_mode == "file" and output_path is not None:
        rows.append(("LaTeX", _format_path(output_path), ""))
    elif output_mode == "directory" and bundle is not None:
        for fragment in bundle.fragments:
            path = fragment.output_path or (
                output_path / f"{fragment.stem}.tex" if output_path else None
            )
            if path is None:
                continue
            rows.append(("Fragment", _format_path(Path(path)), ""))
        if output_path is not None:
            for manifest in _detect_manifests(output_path):
                rows.append(("Manifest", _format_path(manifest), ""))
            for asset in _detect_assets(output_path):
                rows.append(("Asset", _format_path(asset), ""))
            for debug_html in _detect_debug_html(output_path):
                rows.append(("Debug HTML", _format_path(debug_html), ""))

    if rows:
        _render_summary(state, "Conversion Summary", rows)


def present_build_summary(
    *,
    state: CLIState,
    render_result: TemplateRenderResult,
    pdf_path: Path,
) -> None:
    rows = [
        ("Main document", _format_path(render_result.main_tex_path), ""),
        ("PDF", _format_path(pdf_path), ""),
    ]
    for fragment in render_result.fragment_paths:
        rows.append(("Fragment", _format_path(fragment), ""))
    if render_result.bibliography_path is not None:
        rows.append(("Bibliography", _format_path(render_result.bibliography_path), ""))
    build_dir = render_result.main_tex_path.parent
    for manifest in _detect_manifests(build_dir):
        rows.append(("Manifest", _format_path(manifest), ""))
    for asset in _detect_assets(build_dir):
        rows.append(("Asset", _format_path(asset), ""))
    for debug_html in _detect_debug_html(build_dir):
        rows.append(("Debug HTML", _format_path(debug_html), ""))
    _render_summary(state, "Build Outputs", rows)


def _format_message_entry(message: LatexMessage) -> str:
    details = "; ".join(message.details[:2])
    if details:
        return f"{message.summary} ({details})"
    return message.summary


def _render_failure_panel(
    state: CLIState,
    title: str,
    rows: Sequence[tuple[str, str]],
) -> None:
    console = _get_console(state, stderr=True)
    components = _rich_components()
    if console is not None and components is not None:
        box_module, panel_cls, table_cls, text_cls = components
        table = table_cls(box=box_module.SQUARE, show_header=False)
        for label, value in rows:
            table.add_row(text_cls(label, style="bold red"), text_cls(value, style="yellow"))
        console.print(panel_cls(table, box=box_module.SQUARE, title=title, border_style="red"))
        return

    typer.echo(title, err=True)
    for label, value in rows:
        typer.echo(f"  {label}: {value}", err=True)


def present_latexmk_failure(
    *,
    state: CLIState,
    log_path: Path,
    messages: Sequence[LatexMessage],
    open_log: bool,
) -> None:
    errors = [msg for msg in messages if msg.severity is LatexMessageSeverity.ERROR]
    warnings = [msg for msg in messages if msg.severity is LatexMessageSeverity.WARNING]
    rows: list[tuple[str, str]] = []

    primary_entry: str | None = None
    if errors:
        primary_entry = _format_message_entry(errors[0])
    elif warnings:
        primary_entry = _format_message_entry(warnings[-1])
    else:
        parsed = parse_latex_log(log_path)
        if parsed:
            primary_entry = _format_message_entry(parsed[0])

    if primary_entry:
        label = "Primary error" if errors or not warnings else "Last warning"
        rows.append((label, primary_entry))

    rows.append(("Log file", _format_path(log_path)))
    rows.append(("Next steps", "Inspect the log or re-run with --classic-output"))

    _render_failure_panel(state, "latexmk failure", rows)

    if open_log and log_path.exists():  # pragma: no cover - depends on platform
        with contextlib.suppress(Exception):
            typer.launch(str(log_path))


def parse_latex_log(log_path: Path) -> list[LatexMessage]:
    if not log_path.exists():
        return []
    parser = LatexLogParser()
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parser.process_line(line)
    parser.finalize()
    return list(parser.messages)


def consume_event_diagnostics(state: CLIState) -> list[str]:
    verbosity = state.verbosity
    if verbosity <= 0 or not state.events:
        state.events.clear()
        return []

    output_lines: list[str] = []

    if verbosity >= 1:
        slot_events = state.events.get("slot_assignments", [])
        for event in slot_events:
            assignments = event.get("entries", [])
            if not assignments:
                continue
            output_lines.append("Slot assignments:")
            for assignment in assignments:
                document = assignment.get("document", "")
                slot = assignment.get("slot", "")
                selector = assignment.get("selector") or "*"
                include = "include" if assignment.get("include_document") else "extract"
                output_lines.append(f"  - {slot} ← {document} ({selector}, {include})")

        for event in state.events.get("doi_fetch", []):
            value = event.get("value")
            key = event.get("key")
            output_lines.append(f"Fetched DOI {value} for entry '{key}'")

    if verbosity >= 2:
        for event in state.events.get("parser_fallback", []):
            preferred = event.get("preferred", "unknown")
            fallback = event.get("fallback", "unknown")
            output_lines.append(f"Parser fallback: {preferred} → {fallback}")

        for event in state.events.get("template_overrides", []):
            overrides = event.get("values", {})
            if overrides:
                output_lines.append("Template overrides:")
                for key, value in sorted(overrides.items()):
                    output_lines.append(f"  - {key}: {value}")

        for event in state.events.get("conversion_settings", []):
            parser = event.get("parser", "auto")
            copy_assets = event.get("copy_assets")
            manifest = event.get("manifest")
            fallback_enabled = event.get("fallback_converters_enabled")
            output_lines.append(
                f"Settings: parser={parser}, copy_assets={copy_assets}, manifest={manifest}, fallback_converters={fallback_enabled}"
            )
        for event in state.events.get("font_requirements", []):
            required = event.get("required", [])
            missing = event.get("missing", [])
            present = event.get("present", [])
            if missing:
                output_lines.append(f"Font gaps: {', '.join(missing)}")
            output_lines.append(f"Font fallbacks: {', '.join(required) or '<none>'}")
            if present:
                output_lines.append(f"Detected locally: {', '.join(present)}")

    state.events.clear()
    return output_lines


__all__ = [
    "consume_event_diagnostics",
    "parse_latex_log",
    "present_build_summary",
    "present_conversion_summary",
    "present_latexmk_failure",
]
