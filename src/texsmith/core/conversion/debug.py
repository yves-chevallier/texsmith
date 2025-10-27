"""Debug and diagnostic helpers used throughout the conversion pipeline."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..exceptions import LatexRenderingError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConversionCallbacks:
    """Optional hooks used to surface conversion diagnostics."""

    emit_warning: Callable[[str, Exception | None], None] | None = None
    emit_error: Callable[[str, Exception | None], None] | None = None
    debug_enabled: bool = False
    record_event: Callable[[str, Mapping[str, Any]], None] | None = None


class ConversionError(Exception):
    """Raised when a conversion fails and cannot recover."""


def _emit_warning(
    callbacks: ConversionCallbacks | None,
    message: str,
    exception: Exception | None = None,
) -> None:
    if callbacks and callbacks.emit_warning is not None:
        callbacks.emit_warning(message, exception)
    else:  # pragma: no cover - fallback logging
        logger.warning(message)


def _emit_error(
    callbacks: ConversionCallbacks | None,
    message: str,
    exception: Exception | None = None,
) -> None:
    if callbacks and callbacks.emit_error is not None:
        callbacks.emit_error(message, exception)
    else:  # pragma: no cover - fallback logging
        logger.error(message)


def _debug_enabled(callbacks: ConversionCallbacks | None) -> bool:
    return bool(callbacks and callbacks.debug_enabled)


def _fail(
    callbacks: ConversionCallbacks | None,
    message: str,
    exc: Exception,
) -> None:
    _emit_error(callbacks, message, exception=exc)
    raise ConversionError(message) from exc


def _record_event(
    callbacks: ConversionCallbacks | None,
    event: str,
    payload: Mapping[str, Any],
) -> None:
    if callbacks and callbacks.record_event is not None:
        try:
            callbacks.record_event(event, dict(payload))
        except Exception:  # pragma: no cover - defensive
            logger.debug("Failed to record conversion event '%s'", event, exc_info=True)


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


__all__ = [
    "ConversionCallbacks",
    "ConversionError",
    "_record_event",
    "format_rendering_error",
    "persist_debug_artifacts",
    "_debug_enabled",
    "_emit_error",
    "_emit_warning",
    "_fail",
]
