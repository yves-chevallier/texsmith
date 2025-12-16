"""Handlers responsible for assets such as images and diagrams."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
import warnings

from bs4.element import NavigableString, Tag
from requests.utils import requote_uri as requote_url

from texsmith.core.context import RenderContext
from texsmith.core.diagnostics import DiagnosticEmitter
from texsmith.core.exceptions import (
    AssetMissingError,
    InvalidNodeError,
    exception_hint,
    exception_messages,
)
from texsmith.core.rules import RenderPhase, renders
from texsmith.fonts.scripts import render_moving_text

from ..latex.utils import escape_latex_chars
from ..transformers import mermaid2pdf
from ._assets import store_local_image_asset, store_remote_image_asset
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


_MKDOCS_THEME_VARIANTS = {"only-light", "only-dark"}


def _strip_mkdocs_theme_variant(src: str) -> str:
    """Drop MkDocs Material light/dark suffixes appended to image URLs."""
    base, sep, fragment = src.partition("#")
    if not sep:
        return src
    if fragment.lower() in _MKDOCS_THEME_VARIANTS:
        return base
    return src


def _apply_figure_template(
    context: RenderContext,
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
    formatter = getattr(context.formatter, template_name)
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
    latex = formatter(
        path=asset_path,
        caption=caption,
        shortcaption=effective_shortcaption,
        label=label,
        width=width,
        adjustbox=adjustbox,
        link=safe_link,
    )
    return mark_processed(NavigableString(latex))


def _render_mermaid_diagram(
    context: RenderContext,
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
        return mark_processed(NavigableString(f"[{placeholder} unavailable]"))

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

    src = _strip_mkdocs_theme_variant(src)

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

    link_wrapper = None
    link_target = None
    parent = element.parent
    if isinstance(parent, Tag) and parent.name == "a":
        candidates = [
            child
            for child in parent.contents
            if not (isinstance(child, NavigableString) and not child.strip())
        ]
        if len(candidates) == 1 and candidates[0] is element:
            link_wrapper = parent
            link_target = coerce_attribute(parent.get("href"))

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

    if is_valid_url(src):
        stored_path = store_remote_image_asset(context, src)
    else:
        resolved = _resolve_source_path(context, src)
        if resolved is None:
            raise AssetMissingError(f"Unable to resolve image asset '{src}'")

        stored_path = store_local_image_asset(context, resolved)

    figure_node = _apply_figure_template(
        context,
        path=stored_path,
        caption=caption_text,
        alt=alt_text,
        label=None,
        width=width,
        template=template,
        adjustbox=False,
        link=link_target,
    )
    if link_wrapper:
        link_wrapper.replace_with(figure_node)
    else:
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
    width = coerce_attribute(code.get("width") or element.get("width"))
    template = _figure_template_for(element)
    figure_node = _render_mermaid_diagram(context, diagram, template=template, width=width)
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
    width = coerce_attribute(element.get("width"))

    template = _figure_template_for(element)
    figure_node = _render_mermaid_diagram(context, diagram, template=template, width=width)
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
