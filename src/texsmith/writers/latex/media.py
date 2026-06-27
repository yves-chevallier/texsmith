"""Image and Mermaid diagram helpers used by the LaTeX writer.

These functions turn diagram sources into rendered figure nodes. They are
invoked lazily from :mod:`texsmith.writers.latex.writer` through a duck-typed
render context (see ``LaTeXWriter._fake_context``).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any
import warnings

from bs4.element import NavigableString
from requests.utils import requote_uri as requote_url

from texsmith.adapters.html_utils import resolve_asset_path
from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.adapters.transformers import mermaid2pdf
from texsmith.adapters.transformers.mermaid_detect import (
    MERMAID_FILE_SUFFIXES,
    extract_mermaid_live_diagram as _extract_mermaid_live_diagram,
    looks_like_mermaid as _looks_like_mermaid,
)
from texsmith.core.diagnostics import DiagnosticEmitter
from texsmith.core.exceptions import AssetMissingError, exception_hint, exception_messages
from texsmith.fonts.scripts import render_moving_text


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.context import RenderContextLike


def _runtime_emitter(context: RenderContextLike) -> DiagnosticEmitter | None:
    """Return the diagnostic emitter bound to the current runtime, if any."""
    emitter = context.runtime.get("emitter")
    if isinstance(emitter, DiagnosticEmitter):
        return emitter
    return None


def _resolve_source_path(context: RenderContextLike, src: str) -> Path | None:
    """Resolve a local asset path using runtime hints."""
    runtime_dir = context.runtime.get("source_dir")
    if runtime_dir is not None:
        candidate = Path(runtime_dir) / src
        if candidate.exists():
            return candidate.resolve()

    document_path = context.runtime.get("document_path")
    if document_path is not None:
        resolved = resolve_asset_path(Path(document_path), src)
        if resolved is not None:
            return resolved

    project_dir = getattr(context.config, "project_dir", None)
    if project_dir:
        candidate = Path(project_dir) / src
        if candidate.exists():
            return candidate.resolve()

    return None


def _load_mermaid_diagram(context: RenderContextLike, src: str) -> tuple[str, str] | None:
    """Attempt to load a Mermaid diagram from a local file or URL."""
    lowercase = src.lower()
    if lowercase.endswith(MERMAID_FILE_SUFFIXES):
        resolved = _resolve_source_path(context, src)
        if resolved is None:
            raise AssetMissingError(f"Unable to resolve Mermaid diagram '{src}'")
        try:
            return resolved.read_text(encoding="utf-8"), "file"
        except OSError as exc:
            raise AssetMissingError(f"Unable to read Mermaid diagram '{resolved}'") from exc

    diagram = _extract_mermaid_live_diagram(src)
    if diagram is not None:
        return diagram, "url"

    return None


def _mermaid_caption(diagram: str) -> tuple[str | None, str]:
    """Extract caption from the diagram comment header."""
    lines = diagram.splitlines()
    if lines and lines[0].strip().startswith("%%"):
        caption = lines[0].strip()[2:].strip() or None
        body = "\n".join(lines[1:])
        return caption, body
    return None, diagram


def _apply_figure_template(
    context: RenderContextLike,
    *,
    path: Path,
    caption: str | None = None,
    shortcaption: str | None = None,
    alt: str | None = None,
    label: str | None = None,
    width: str | None = None,
    template: str | None = None,
    adjustbox: bool = False,
    link: str | None = None,
) -> NavigableString:
    """Render the shared figure template and return a new node."""
    template_name = template or context.runtime.get("figure_template", "figure")
    asset_path = context.assets.latex_path(path)
    legacy_accents = getattr(context.config, "legacy_latex_accents", False)
    caption = render_moving_text(caption, context, legacy_accents=legacy_accents, wrap_scripts=True)
    shortcaption = render_moving_text(
        shortcaption, context, legacy_accents=legacy_accents, wrap_scripts=True
    )
    alt_text = render_moving_text(alt, context, legacy_accents=legacy_accents, wrap_scripts=True)
    effective_shortcaption = shortcaption or alt_text or caption
    safe_link = (
        escape_latex_chars(requote_url(link), legacy_accents=legacy_accents) if link else None
    )
    latex = context.formatter.render_template(
        template_name,
        path=asset_path,
        caption=caption,
        shortcaption=effective_shortcaption,
        label=label,
        width=width,
        adjustbox=adjustbox,
        link=safe_link,
    )
    return NavigableString(latex)


def _warn_mermaid_failure(context: RenderContextLike, exc: Exception) -> None:
    """Emit a CLI-friendly warning describing Mermaid rendering failures."""
    emitter = _runtime_emitter(context)
    guidance = (
        "Install Docker and the 'minlag/mermaid-cli' image (or register a custom Mermaid "
        "converter) to enable diagram rendering."
    )
    summary = "Mermaid diagram could not be rendered. TexSmith inserted a placeholder instead."
    hint = exception_hint(exc)

    if emitter is None:
        detail = f" ({hint})" if hint else ""
        message = f"{summary}{detail}. {guidance}"
        warnings.warn(message, stacklevel=3)
        return

    if emitter.debug_enabled:
        chain = exception_messages(exc)
        detail_block = ""
        if chain:
            detail_lines = "\n".join(f"- {line}" for line in chain)
            detail_block = f"\nDetails:\n{detail_lines}"
        emitter.warning(f"{summary}{detail_block}\n{guidance}", exc=exc)
        return

    detail = f" ({hint})" if hint else ""
    emitter.warning(f"{summary}{detail}. {guidance} Run with --debug for technical details.")


def _render_mermaid_diagram(
    context: RenderContextLike,
    diagram: str,
    *,
    template: str | None = None,
    caption: str | None = None,
    width: str | None = None,
) -> NavigableString | None:
    """Render a Mermaid diagram and return the resulting LaTeX node."""
    extracted_caption, body = _mermaid_caption(diagram)
    effective_caption = extracted_caption if extracted_caption is not None else caption
    if not context.runtime.get("copy_assets", True):
        placeholder = effective_caption or "Mermaid diagram"
        return NavigableString(placeholder)
    if not _looks_like_mermaid(body):
        return None
    if "```" in body or "~~~" in body:
        return None

    render_options: dict[str, Any] = {}
    mermaid_config = getattr(context.config, "mermaid_config", None)
    if mermaid_config:
        project_dir = getattr(context.config, "project_dir", None)
        if project_dir is None:
            raise AssetMissingError("Project directory required to render Mermaid diagrams")
        render_options["config_filename"] = Path(project_dir) / mermaid_config
    backend = context.runtime.get("diagrams_backend")
    if backend:
        render_options["backend"] = backend
    runtime_mermaid_config = context.runtime.get("mermaid_config")
    if runtime_mermaid_config is not None:
        render_options["mermaid_config"] = runtime_mermaid_config

    try:
        artefact = mermaid2pdf(body, output_dir=context.assets.output_root, **render_options)
    except Exception as exc:  # pragma: no cover - safeguard
        _warn_mermaid_failure(context, exc)
        placeholder = effective_caption or "Mermaid diagram"
        return NavigableString(f"[{placeholder} unavailable]")

    asset_key = f"mermaid::{hashlib.sha256(body.encode('utf-8')).hexdigest()}"
    stored_path = context.assets.register(asset_key, artefact)

    return _apply_figure_template(
        context,
        path=stored_path,
        caption=effective_caption,
        label=None,
        width=width,
        template=template,
        adjustbox=True,
    )
