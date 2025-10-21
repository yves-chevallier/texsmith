"""Handlers responsible for assets such as images and diagrams."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from bs4 import NavigableString, Tag

from ..context import RenderContext
from ..exceptions import AssetMissingError, InvalidNodeError
from ..rules import RenderPhase, renders
from ..transformers import (
    drawio2pdf,
    fetch_image,
    image2pdf,
    mermaid2pdf,
    svg2pdf,
)
from ..utils import is_valid_url, resolve_asset_path


MERMAID_KEYWORDS = (
    "graph ",
    "graph\t",
    "flowchart ",
    "flowchart\t",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "gantt",
    "erDiagram",
    "journey",
)


def _figure_template_for(element: Tag) -> str | None:
    """Determine which figure template to use based on ancestor metadata."""

    current = element
    while current is not None:
        classes = getattr(current, "get", lambda *_: None)("class") or []
        if isinstance(classes, str):
            class_list = classes.split()
        else:
            class_list = list(classes)
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
) -> NavigableString:
    """Render the shared figure template and return a new node."""

    template_name = template or context.runtime.get("figure_template", "figure")
    formatter = getattr(context.formatter, template_name)
    latex = formatter(
        path=path.name,
        caption=caption,
        shortcaption=caption,
        label=label,
        width=width,
    )
    node = NavigableString(latex)
    setattr(node, "processed", True)
    return node


def _render_mermaid_diagram(
    context: RenderContext,
    diagram: str,
    *,
    template: str | None = None,
) -> NavigableString | None:
    """Render a Mermaid diagram and return the resulting LaTeX node."""

    caption, body = _mermaid_caption(diagram)
    if not context.runtime.get("copy_assets", True):
        placeholder = caption or "Mermaid diagram"
        node = NavigableString(placeholder)
        setattr(node, "processed", True)
        return node
    if not _looks_like_mermaid(body):
        return None

    render_options: dict[str, Any] = {}
    mermaid_config = getattr(context.config, "mermaid_config", None)
    if mermaid_config:
        project_dir = getattr(context.config, "project_dir", None)
        if project_dir is None:
            raise AssetMissingError(
                "Project directory required to render Mermaid diagrams"
            )
        render_options["config_filename"] = Path(project_dir) / mermaid_config

    artefact = mermaid2pdf(
        body, output_dir=context.assets.output_root, **render_options
    )

    asset_key = f"mermaid::{hashlib.sha256(body.encode('utf-8')).hexdigest()}"
    stored_path = context.assets.register(asset_key, artefact)

    return _apply_figure_template(
        context,
        path=stored_path,
        caption=caption,
        label=None,
        width=None,
        template=template,
    )


def _mermaid_caption(diagram: str) -> tuple[str | None, str]:
    """Extract caption from the diagram comment header."""

    lines = diagram.splitlines()
    if lines and lines[0].strip().startswith("%%"):
        caption = lines[0].strip()[2:].strip() or None
        body = "\n".join(lines[1:])
        return caption, body
    return None, diagram


def _looks_like_mermaid(diagram: str) -> bool:
    """Heuristically detect Mermaid diagrams."""

    lower = diagram.lstrip().lower()
    return any(keyword in lower for keyword in MERMAID_KEYWORDS)


@renders("img", phase=RenderPhase.BLOCK, name="render_images", nestable=False)
def render_images(element: Tag, context: RenderContext) -> None:
    """Convert <img> nodes into LaTeX figures and manage assets."""

    if not context.runtime.get("copy_assets", True):
        alt_text = element.get("alt") or element.get("title") or ""
        placeholder = alt_text.strip() or "[image]"
        node = NavigableString(placeholder)
        setattr(node, "processed", True)
        element.replace_with(node)
        return

    src = element.get("src")
    if not src:
        raise InvalidNodeError("Image tag without 'src' attribute")

    classes = element.get("class") or []
    if {"twemoji", "emojione"}.intersection(classes):
        return

    if element.find_parent("figure"):
        return

    alt_text = element.get("alt") or None
    width = element.get("width") or None
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

    template = _figure_template_for(element)

    figure_node = _apply_figure_template(
        context,
        path=stored_path,
        caption=alt_text,
        label=None,
        width=width,
        template=template,
    )
    element.replace_with(figure_node)


@renders("div", phase=RenderPhase.BLOCK, name="render_mermaid", nestable=False)
def render_mermaid(element: Tag, context: RenderContext) -> None:
    """Convert Mermaid code blocks inside highlight containers."""

    classes = element.get("class") or []
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

    classes = element.get("class") or []
    if "mermaid" not in classes:
        return

    diagram = element.get_text()
    template = _figure_template_for(element)
    figure_node = _render_mermaid_diagram(context, diagram, template=template)
    if figure_node is None:
        return

    element.replace_with(figure_node)
