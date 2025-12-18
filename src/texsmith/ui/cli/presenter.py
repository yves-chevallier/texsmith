"""Rich-aware presenters for CLI output and diagnostics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from texsmith.adapters.latex.engines import (
    LatexMessage,
    LatexMessageSeverity,
    parse_latex_log,
)
from texsmith.api.pipeline import ConversionBundle
from texsmith.api.templates import TemplateRenderResult

from .state import CLIState


if TYPE_CHECKING:  # pragma: no cover - typing only
    from rich.console import Console


def _get_console(state: CLIState, *, stderr: bool = False) -> Console | None:
    """Retrieve the active Rich console from the CLI state if available.

    This helper ensures that we respect the user's stream preference (stdout vs stderr)
    and gracefully handle cases where the console hasn't been initialized or is
    running in a non-interactive environment.
    """
    try:
        console = state.err_console if stderr else state.console
    except Exception:  # pragma: no cover - fallback when Rich unavailable
        return None
    if getattr(console, "is_terminal", False):
        return console
    return None


def _rich_components() -> tuple[Any, Any, Any, Any] | None:
    """Import and return Rich components if the library is installed.

    This allows the CLI to degrade gracefully on systems where `rich` is missing,
    falling back to plain text output instead of crashing.
    """
    try:
        from rich import box
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
    except ImportError:  # pragma: no cover - Rich absent
        return None
    return box, Panel, Table, Text


def _build_table(
    *,
    title: str | None,
    columns: Sequence[str],
    header_style: str = "bold cyan",
    box_style: Any | None = None,
) -> tuple[Any, Any, Any] | tuple[None, None, None]:
    """Create a Rich table with the house style."""
    components = _rich_components()
    if components is None:
        return None, None, None
    box_module, _panel_cls, table_cls, text_cls = components
    table = table_cls(
        title=title or None,
        box=box_style or box_module.SQUARE,
        show_edge=True,
        header_style=header_style,
    )
    for col in columns:
        table.add_column(col)
    return table, text_cls, box_module


def _format_path(path: Path) -> str:
    """Format a path relative to the current working directory for display.

    Using relative paths reduces visual noise in console output, making it easier
    for users to identify files within their project structure.
    """
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(Path.cwd()))
    except ValueError:
        return str(resolved)


def _colorize_location(text_cls: Any, *, artifact: str, location: str) -> Any:
    """Apply per-artifact coloring to locations for Rich tables."""
    lower_loc = location.lower()
    suffixes = {
        "tex": "bright_cyan",
        "pdf": "bright_green",
        "sty": "yellow",
        "cls": "yellow",
    }
    image_suffixes = {"png", "jpg", "jpeg", "gif", "svg", "bmp", "webp"}
    style: str | None = None
    for suffix, mapped in suffixes.items():
        if lower_loc.endswith(f".{suffix}"):
            style = mapped
            break
    if style is None and (
        any(lower_loc.endswith(f".{ext}") for ext in image_suffixes)
        or artifact.lower() == "asset"
        or "/assets/" in lower_loc
        or lower_loc.startswith("assets")
    ):
        style = "magenta"
    return text_cls(location, style=style) if style else text_cls(location)


def _size_details(path: Path) -> str:
    """Return a human-readable size for a file if it exists."""
    try:
        stat = path.stat()
    except OSError:
        return ""
    if not path.is_file():
        return ""
    size = stat.st_size
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MiB"
    if size >= 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size} B"


def _align_size_rows(rows: Sequence[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Pad size strings so decimal points line up."""
    enriched: list[tuple[str, str, str, str | None, str | None, str | None]] = []
    max_left = 0
    max_right = 0
    for artifact, location, detail in rows:
        if detail:
            tokens = detail.split()
            num = tokens[0]
            tail = " ".join(tokens[1:]) if len(tokens) > 1 else ""
            if "." in num:
                left, right = num.split(".", 1)
            else:
                left, right = num, ""
            max_left = max(max_left, len(left))
            max_right = max(max_right, len(right))
            enriched.append((artifact, location, detail, left, right, tail))
        else:
            enriched.append((artifact, location, detail, None, None, None))

    if max_left == 0 and max_right == 0:
        return list(rows)

    aligned: list[tuple[str, str, str]] = []
    for artifact, location, detail, left, right, tail in enriched:
        if detail and left is not None and right is not None:
            padded_left = left.rjust(max_left)
            padded_right = right.ljust(max_right)
            if max_right:
                if right:
                    number = f"{padded_left}.{padded_right}".rstrip()
                else:
                    number = f"{padded_left} {' ' * (max_right + 1)}".rstrip()
            else:
                number = padded_left
            padded = f"{number} {tail}".rstrip()
            aligned.append((artifact, location, padded))
        else:
            aligned.append((artifact, location, detail))
    return aligned


def _render_summary(state: CLIState, title: str, rows: Sequence[tuple[str, str, str]]) -> None:
    """Display a summary table of generated artifacts.

    This provides the user with a high-level overview of what was created and where,
    saving them from having to manually check the output directory.
    """
    rows = _align_size_rows(rows)
    console = _get_console(state)
    components = _rich_components()
    has_details = any(bool(details) for _, _, details in rows)
    if console is not None and components is not None:
        box_module, _panel_cls, table_cls, text_cls = components
        table = table_cls(box=box_module.SQUARE, header_style="bold cyan")
        if title:
            table.title = title
        table.add_column("Artifact", style="cyan")
        table.add_column("Location")
        if has_details:
            table.add_column("Filesize", style="magenta", justify="right", no_wrap=True)
        for artifact, location, details in rows:
            location_cell = _colorize_location(text_cls, artifact=artifact, location=location)
            if has_details:
                table.add_row(artifact, location_cell, details)
            else:
                table.add_row(artifact, location_cell)
        console.print(table)
        return

    # Plain-text fallback
    if title:
        typer.echo(title)
    for artifact, location, details in rows:
        suffix = f" — {details}" if details else ""
        typer.echo(f"  * {artifact}: {location}{suffix}")


def present_rule_descriptions(state: CLIState, rules: Sequence[Mapping[str, Any]]) -> None:
    """Render a diagnostic view of registered render rules."""
    if not rules:
        return

    console = _get_console(state)
    if console is not None:
        table, _text_cls, box_module = _build_table(
            title="Registered Rules",
            columns=["Phase", "Tag", "Name", "Priority", "Before", "After"],
        )
        if table is not None and box_module is not None:
            for entry in rules:
                table.add_row(
                    str(entry.get("phase", "")),
                    str(entry.get("tag", "")),
                    str(entry.get("name", "")),
                    str(entry.get("priority", "")),
                    ", ".join(entry.get("before", []) or []),
                    ", ".join(entry.get("after", []) or []),
                )
            console.print(table)
            return

    typer.echo("Registered Rules:")
    for entry in rules:
        before = ", ".join(entry.get("before", []) or [])
        after = ", ".join(entry.get("after", []) or [])
        typer.echo(
            f"  - {entry.get('phase', '')}/{entry.get('tag', '')}: {entry.get('name', '')} "
            f"(priority={entry.get('priority', '')}, before=[{before}], after=[{after}])"
        )


def _normalise_script_usage(
    usage: Sequence[Mapping[str, Any]] | None,
) -> list[Mapping[str, Any]]:
    normalised: list[Mapping[str, Any]] = []
    for entry in usage or []:
        slug = entry.get("slug") if isinstance(entry, Mapping) else None
        if not slug:
            continue
        normalised.append(entry)
    return normalised


def present_fonts_info(state: CLIState, render_result: TemplateRenderResult) -> None:
    """Display a table of detected fallback fonts."""
    template_context = getattr(render_result, "context", {}) or {}
    fonts_section = template_context.get("fonts") if isinstance(template_context, Mapping) else {}
    usage = _normalise_script_usage(
        fonts_section.get("script_usage") if isinstance(fonts_section, Mapping) else []
    )
    if not usage:
        usage = _normalise_script_usage(getattr(render_result.document_state, "script_usage", []))
    if not usage:
        console = _get_console(state)
        components = _rich_components()
        if console is not None and components is not None:
            box_module, panel_cls, _table_cls, text_cls = components
            console.print(
                panel_cls(
                    text_cls("No fallback fonts detected; base fonts only.", style="dim"),
                    box=box_module.SIMPLE,
                    border_style="cyan",
                )
            )
            return
        typer.echo("No fallback fonts detected; base fonts only.")
        return

    console = _get_console(state)
    if console is not None:
        table, _text_cls, _box_module = _build_table(
            title="Fallback Fonts",
            columns=["Script", "Text Cmd", "Font Cmd", "Codepoints", "Font Name"],
        )
        if table is not None:
            for entry in usage:
                count = entry.get("count")
                count_text = str(int(count)) if isinstance(count, (int, float)) else ""
                table.add_row(
                    str(entry.get("group") or entry.get("slug") or ""),
                    f"\\{entry.get('text_command')}" if entry.get("text_command") else "",
                    f"\\{entry.get('font_command')}" if entry.get("font_command") else "",
                    count_text,
                    str(entry.get("font_name") or ""),
                )
            console.print(table)
            return

    typer.echo("Fallback Fonts:")
    for entry in usage:
        script = entry.get("group") or entry.get("slug") or ""
        text_cmd = entry.get("text_command") or ""
        font_cmd = entry.get("font_command") or ""
        font_name = entry.get("font_name") or ""
        count = entry.get("count")
        count_text = f" [{int(count)}]" if isinstance(count, (int, float)) else ""
        typer.echo(
            f"  - {script}: \\{text_cmd or '?'} -> \\{font_cmd or '?'} ({font_name}){count_text}"
        )


def present_context_attributes(state: CLIState, render_result: TemplateRenderResult) -> None:
    """Display resolved context attributes with emitters and consumers."""

    entries = getattr(render_result, "context_attributes", []) or []
    if not entries:
        typer.echo("No context attributes recorded.")
        return

    console = _get_console(state)
    components = _rich_components()
    if console is not None and components is not None:
        table, _text_cls, _box_module = _build_table(
            title="Template Context",
            columns=["Key", "Emitters", "Consumers", "Value"],
        )
        if table is not None:
            for entry in entries:
                emitters = "\n".join(entry.get("emitters", []) or [])
                consumers = "\n".join(entry.get("consumers", []) or [])
                table.add_row(
                    str(entry.get("name", "")),
                    emitters or "-",
                    consumers or "-",
                    str(entry.get("value", "")),
                )
            console.print(table)
            return

    typer.echo("Context attributes:")
    for entry in entries:
        emitters_list = entry.get("emitters", []) or ["-"]
        consumers_list = entry.get("consumers", []) or ["-"]
        emitters = "\n    ".join(emitters_list)
        consumers = "\n    ".join(consumers_list)
        typer.echo(
            f"  - {entry.get('name', '')}:\n"
            f"    emitters: {emitters}\n"
            f"    consumers: {consumers}\n"
            f"    value: {entry.get('value', '')}"
        )


def _detect_assets(directory: Path) -> list[Path]:
    """Find asset files in the given directory.

    We report these to the user so they know which static resources (images, fonts)
    were successfully copied or generated alongside their document.
    """
    assets_dir = directory / "assets"
    if not assets_dir.is_dir():
        return []
    return sorted(
        (path for path in assets_dir.rglob("*") if path.is_file()),
        key=lambda p: p.relative_to(assets_dir).as_posix().lower(),
    )


def _detect_ts_packages(directory: Path) -> list[Path]:
    """Detect generated ts-* packages to highlight them in the summary."""
    candidates = [
        directory / "ts-fonts.sty",
        directory / "ts-glossary.sty",
    ]
    return [path for path in candidates if path.is_file()]


def _detect_manifests(directory: Path) -> list[Path]:
    """Find manifest files in the given directory.

    Manifests contain machine-readable metadata about the build. Detecting and
    reporting them confirms to the user that the build metadata was correctly persisted.
    """
    return sorted(path for path in directory.glob("*.json") if "manifest" in path.name.lower())


def _detect_debug_html(directory: Path) -> list[Path]:
    """Find debug HTML snapshots in the given directory.

    These snapshots are crucial for troubleshooting rendering issues. Pointing them
    out explicitly helps users find the diagnostic information they need.
    """
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
        rows.append(
            (
                "Main document",
                _format_path(render_result.main_tex_path),
                _size_details(render_result.main_tex_path),
            )
        )
        for fragment in render_result.fragment_paths:
            rows.append(("Fragment", _format_path(fragment), _size_details(fragment)))
        if render_result.bibliography_path is not None:
            rows.append(
                (
                    "Bibliography",
                    _format_path(render_result.bibliography_path),
                    _size_details(render_result.bibliography_path),
                )
            )
        for package in _detect_ts_packages(main_dir):
            rows.append(
                (
                    package.stem,
                    _format_path(package),
                    _size_details(package),
                )
            )
        for manifest in _detect_manifests(main_dir):
            rows.append(("Manifest", _format_path(manifest), _size_details(manifest)))
        for asset in _detect_assets(main_dir):
            rows.append(("Asset", _format_path(asset), _size_details(asset)))
        for debug_html in _detect_debug_html(main_dir):
            rows.append(("Debug HTML", _format_path(debug_html), _size_details(debug_html)))
        _render_summary(state, "", rows)
        return

    if output_mode == "file" and output_path is not None:
        rows.append(("LaTeX", _format_path(output_path), _size_details(output_path)))
    elif output_mode == "directory" and bundle is not None:
        for fragment in bundle.fragments:
            path = fragment.output_path or (
                output_path / f"{fragment.stem}.tex" if output_path else None
            )
            if path is None:
                continue
            rows.append(("Fragment", _format_path(Path(path)), _size_details(Path(path))))
        if output_path is not None:
            for manifest in _detect_manifests(output_path):
                rows.append(("Manifest", _format_path(manifest), _size_details(manifest)))
            for asset in _detect_assets(output_path):
                rows.append(("Asset", _format_path(asset), _size_details(asset)))
            for debug_html in _detect_debug_html(output_path):
                rows.append(("Debug HTML", _format_path(debug_html), _size_details(debug_html)))

    if rows:
        _render_summary(state, "Conversion Summary", rows)


def present_html_summary(
    *,
    state: CLIState,
    output_mode: str,
    output_paths: list[Path],
) -> None:
    rows: list[tuple[str, str, str]] = []
    if output_mode == "file" and output_paths:
        rows.append(("HTML", _format_path(output_paths[0]), _size_details(output_paths[0])))
    elif output_mode in {"directory", "template"}:
        for path in output_paths:
            rows.append(("HTML", _format_path(path), _size_details(path)))
    if rows:
        _render_summary(state, "HTML Output", rows)


def present_build_summary(
    *,
    state: CLIState,
    render_result: TemplateRenderResult,
    pdf_path: Path,
) -> None:
    rows = [
        (
            "Main document",
            _format_path(render_result.main_tex_path),
            _size_details(render_result.main_tex_path),
        ),
        ("PDF", _format_path(pdf_path), _size_details(pdf_path)),
    ]
    for fragment in render_result.fragment_paths:
        rows.append(("Fragment", _format_path(fragment), _size_details(fragment)))
    if render_result.bibliography_path is not None:
        rows.append(
            (
                "Bibliography",
                _format_path(render_result.bibliography_path),
                _size_details(render_result.bibliography_path),
            )
        )
    build_dir = render_result.main_tex_path.parent
    for package in _detect_ts_packages(build_dir):
        rows.append((package.stem, _format_path(package), _size_details(package)))
    for manifest in _detect_manifests(build_dir):
        rows.append(("Manifest", _format_path(manifest), _size_details(manifest)))
    for asset in _detect_assets(build_dir):
        rows.append(("Asset", _format_path(asset), _size_details(asset)))
    for debug_html in _detect_debug_html(build_dir):
        rows.append(("Debug HTML", _format_path(debug_html), _size_details(debug_html)))
    _render_summary(state, "", rows)


def _format_message_entry(message: LatexMessage) -> str:
    """Format a LaTeX log message for display in the failure panel.

    This condenses complex LaTeX log entries into a single, readable line,
    stripping unnecessary details to help the user focus on the primary error.
    """
    details = "; ".join(message.details[:2])
    if details:
        return f"{message.summary} ({details})"
    return message.summary


def _render_failure_panel(
    state: CLIState,
    title: str,
    rows: Sequence[tuple[str, str]],
) -> None:
    """Display a failure diagnostic panel.

    This panel highlights the critical error and suggests next steps, helping
    users diagnose build failures quickly without wading through raw logs.
    """
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


def present_latex_failure(
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

    _render_failure_panel(state, "LaTeX failure", rows)

    if open_log and log_path.exists():  # pragma: no cover - depends on platform
        with contextlib.suppress(Exception):
            typer.launch(str(log_path))


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
    "present_build_summary",
    "present_conversion_summary",
    "present_html_summary",
    "present_latex_failure",
    "present_rule_descriptions",
]
