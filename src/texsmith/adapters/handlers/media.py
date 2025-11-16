"""Handlers responsible for assets such as images and diagrams."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
import warnings

from bs4.element import NavigableString, Tag

from texsmith.core.context import RenderContext
from texsmith.core.diagnostics import DiagnosticEmitter
from texsmith.core.exceptions import (
    AssetMissingError,
    InvalidNodeError,
    exception_hint,
    exception_messages,
)
from texsmith.core.rules import RenderPhase, renders

from ..transformers import (
    drawio2pdf,
    fetch_image,
    image2pdf,
    mermaid2pdf,
    svg2pdf,
)
from ._helpers import (
    coerce_attribute,
    gather_classes,
    is_valid_url,
    mark_processed,
    resolve_asset_path,
)
from ._mermaid import (
    MERMAID_FILE_SUFFIXES,
    extract_mermaid_live_diagram as _extract_mermaid_live_diagram,
    looks_like_mermaid as _looks_like_mermaid,
)


def _runtime_emitter(context: RenderContext) -> DiagnosticEmitter | None:
    """Return the diagnostic emitter bound to the current runtime, if any."""
    emitter = context.runtime.get("emitter")
    if isinstance(emitter, DiagnosticEmitter):
        return emitter
    return None


def _load_mermaid_diagram(context: RenderContext, src: str) -> tuple[str, str] | None:
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


def _figure_template_for(element: Tag) -> str | None:
    """Determine which figure template to use based on ancestor metadata."""
    current = element
    while current is not None:
        raw_classes = getattr(current, "get", lambda *_: None)("class")
        class_list = gather_classes(raw_classes)
        if any(cls in {"admonition", "exercise"} for cls in class_list):
            return "figure_tcolorbox"
        if getattr(current, "name", None) == "details":
            return "figure_tcolorbox"
        current = getattr(current, "parent", None)
    return None


def _resolve_source_path(context: RenderContext, src: str) -> Path | None:
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


def _apply_figure_template(
    context: RenderContext,
    *,
    path: Path,
    caption: str | None = None,
    label: str | None = None,
    width: str | None = None,
    template: str | None = None,
    adjustbox: bool = False,
) -> NavigableString:
    """Render the shared figure template and return a new node."""
    template_name = template or context.runtime.get("figure_template", "figure")
    formatter = getattr(context.formatter, template_name)
    asset_path = context.assets.latex_path(path)
    latex = formatter(
        path=asset_path,
        caption=caption,
        shortcaption=caption,
        label=label,
        width=width,
        adjustbox=adjustbox,
    )
    return mark_processed(NavigableString(latex))


def _render_mermaid_diagram(
    context: RenderContext,
    diagram: str,
    *,
    template: str | None = None,
    caption: str | None = None,
) -> NavigableString | None:
    """Render a Mermaid diagram and return the resulting LaTeX node."""
    extracted_caption, body = _mermaid_caption(diagram)
    effective_caption = extracted_caption if extracted_caption is not None else caption
    if not context.runtime.get("copy_assets", True):
        placeholder = effective_caption or "Mermaid diagram"
        return mark_processed(NavigableString(placeholder))
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

    try:
        artefact = mermaid2pdf(body, output_dir=context.assets.output_root, **render_options)
    except Exception as exc:  # pragma: no cover - safeguard
        _warn_mermaid_failure(context, exc)
        placeholder = effective_caption or "Mermaid diagram"
        return mark_processed(NavigableString(f"[{placeholder} unavailable]"))

    asset_key = f"mermaid::{hashlib.sha256(body.encode('utf-8')).hexdigest()}"
    stored_path = context.assets.register(asset_key, artefact)

    return _apply_figure_template(
        context,
        path=stored_path,
        caption=effective_caption,
        label=None,
        width=None,
        template=template,
        adjustbox=True,
    )


def _mermaid_caption(diagram: str) -> tuple[str | None, str]:
    """Extract caption from the diagram comment header."""
    lines = diagram.splitlines()
    if lines and lines[0].strip().startswith("%%"):
        caption = lines[0].strip()[2:].strip() or None
        body = "\n".join(lines[1:])
        return caption, body
    return None, diagram


@renders("img", phase=RenderPhase.BLOCK, name="render_images", nestable=False)
def render_images(element: Tag, context: RenderContext) -> None:
    """Convert <img> nodes into LaTeX figures and manage assets."""
    if not context.runtime.get("copy_assets", True):
        alt_text = (
            coerce_attribute(element.get("alt")) or coerce_attribute(element.get("title")) or ""
        )
        placeholder = alt_text.strip() or "[image]"
        element.replace_with(mark_processed(NavigableString(placeholder)))
        return

    src = coerce_attribute(element.get("src"))
    if not src:
        raise InvalidNodeError("Image tag without 'src' attribute")

    classes = gather_classes(element.get("class"))
    if {"twemoji", "emojione"}.intersection(classes):
        return

    if element.find_parent("figure"):
        return

    raw_alt = coerce_attribute(element.get("alt"))
    alt_text = raw_alt.strip() if raw_alt else None
    raw_title = coerce_attribute(element.get("title"))
    caption_text = raw_title.strip() if raw_title else None
    width = coerce_attribute(element.get("width")) or None
    template = _figure_template_for(element)

    mermaid_payload = _load_mermaid_diagram(context, src)
    if mermaid_payload is not None:
        diagram, _ = mermaid_payload
        figure_node = _render_mermaid_diagram(
            context,
            diagram,
            template=template,
            caption=caption_text,
        )
        if figure_node is None:
            raise InvalidNodeError(f"Mermaid source '{src}' does not contain a valid diagram")
        element.replace_with(figure_node)
        return

    if not caption_text:
        caption_text = alt_text

    asset_key = src

    if is_valid_url(src):
        artefact = fetch_image(src, output_dir=context.assets.output_root)
    else:
        resolved = _resolve_source_path(context, src)
        if resolved is None:
            raise AssetMissingError(f"Unable to resolve image asset '{src}'")

        match resolved.suffix.lower():
            case ".svg":
                artefact = svg2pdf(resolved, output_dir=context.assets.output_root)
            case ".drawio":
                artefact = drawio2pdf(resolved, output_dir=context.assets.output_root)
            case _:
                artefact = image2pdf(resolved, output_dir=context.assets.output_root)

        asset_key = str(resolved)

    stored_path = context.assets.register(asset_key, artefact)

    figure_node = _apply_figure_template(
        context,
        path=stored_path,
        caption=caption_text,
        label=None,
        width=width,
        template=template,
        adjustbox=False,
    )
    element.replace_with(figure_node)


@renders("div", phase=RenderPhase.BLOCK, name="render_mermaid", nestable=False)
def render_mermaid(element: Tag, context: RenderContext) -> None:
    """Convert Mermaid code blocks inside highlight containers."""
    classes = gather_classes(element.get("class"))
    if "highlight" not in classes and "mermaid" not in classes:
        return

    code = element.find("code")
    if code is None:
        return

    diagram = code.get_text()
    template = _figure_template_for(element)
    figure_node = _render_mermaid_diagram(context, diagram, template=template)
    if figure_node is None:
        return

    element.replace_with(figure_node)


@renders("pre", phase=RenderPhase.BLOCK, name="render_mermaid_pre", nestable=False)
def render_mermaid_pre(element: Tag, context: RenderContext) -> None:
    """Handle <pre class=\"mermaid\"> blocks."""
    classes = gather_classes(element.get("class"))
    if "mermaid" not in classes:
        return

    diagram: str | None = None
    source_hint = coerce_attribute(element.get("data-mermaid-source"))
    if source_hint:
        payload = _load_mermaid_diagram(context, source_hint)
        if payload is not None:
            diagram, _ = payload
    if diagram is None:
        diagram = element.get_text()

    template = _figure_template_for(element)
    figure_node = _render_mermaid_diagram(context, diagram, template=template)
    if figure_node is None:
        return

    element.replace_with(figure_node)


def _warn_mermaid_failure(context: RenderContext, exc: Exception) -> None:
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
