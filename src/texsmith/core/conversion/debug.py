"""Debug and diagnostic helpers used throughout the conversion pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..diagnostics import DiagnosticEmitter, LoggingEmitter, NullEmitter
from ..exceptions import LatexRenderingError, exception_hint


class ConversionError(Exception):
    """Raised when a conversion fails and cannot recover."""


def ensure_emitter(emitter: DiagnosticEmitter | None) -> DiagnosticEmitter:
    """Return a usable emitter, defaulting to the null implementation."""
    return emitter if emitter is not None else NullEmitter()


def debug_enabled(emitter: DiagnosticEmitter | None) -> bool:
    """Return whether debug mode is active for the given emitter."""
    return bool(emitter and getattr(emitter, "debug_enabled", False))


def raise_conversion_error(
    emitter: DiagnosticEmitter | None,
    message: str,
    exc: Exception,
) -> None:
    """Emit an error diagnostic before raising a conversion failure."""
    ensure_emitter(emitter).error(message, exc)
    error = ConversionError(message)
    error._texsmith_logged = True  # noqa: SLF001
    raise error from exc


def record_event(
    emitter: DiagnosticEmitter | None,
    event: str,
    payload: Mapping[str, Any],
) -> None:
    """Forward a structured diagnostic event."""
    ensure_emitter(emitter).event(event, payload)


def persist_debug_artifacts(output_dir: Path, source: Path, html: str) -> None:
    """Persist intermediate HTML snapshots to aid debugging."""
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_path = output_dir / f"{source.stem}.debug.html"
    debug_path.write_text(html, encoding="utf-8")


def format_rendering_error(error: LatexRenderingError) -> str:
    """Format a human-readable rendering failure summary."""
    cause = error.__cause__
    if cause is None:
        return str(error)
    return f"LaTeX rendering failed: {cause}"


def format_user_friendly_render_error(error: LatexRenderingError) -> str:
    """Return a concise rendering failure summary suitable for end users."""
    summary = "LaTeX rendering failed"
    hint_source = error.__cause__ or error
    hint = exception_hint(hint_source)
    if hint:
        summary = f"{summary}: {hint}"
    if summary.endswith("."):
        summary = summary.rstrip(".")
    return f"{summary}. Re-run with --debug for technical details."


__all__ = [
    "ConversionError",
    "DiagnosticEmitter",
    "LoggingEmitter",
    "NullEmitter",
    "debug_enabled",
    "ensure_emitter",
    "format_rendering_error",
    "format_user_friendly_render_error",
    "persist_debug_artifacts",
    "raise_conversion_error",
    "record_event",
]
