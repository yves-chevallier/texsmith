"""Handlers responsible for assets such as images and diagrams."""

from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import zlib

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


MERMAID_FILE_SUFFIXES = (".mmd", ".mermaid")


def _decode_mermaid_pako(payload: str) -> str:
    """Decode a Mermaid Live pako payload into plain text."""

    token = payload.strip()
    if not token:
        raise InvalidNodeError("Mermaid payload is empty")

    padding = (-len(token)) % 4
    if padding:
        token += "=" * padding

    try:
        compressed = base64.urlsafe_b64decode(token)
    except (binascii.Error, ValueError) as exc:
        raise InvalidNodeError("Mermaid payload is not valid base64") from exc

    last_error: Exception | None = None
    for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
        try:
            data = zlib.decompress(compressed, wbits=wbits)
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise InvalidNodeError("Mermaid payload is not UTF-8 text") from exc
        except zlib.error as exc:
            last_error = exc

    raise InvalidNodeError("Unable to decompress Mermaid payload") from last_error


def _extract_mermaid_live_diagram(src: str) -> str | None:
    """Return Mermaid source encoded in a mermaid.live URL."""

    try:
        parsed = urlparse(src)
    except ValueError:
        return None

    if not parsed.netloc or not parsed.scheme:
        return None
    if not parsed.netloc.endswith("mermaid.live"):
        return None

    fragment = (parsed.fragment or "").strip()
    if not fragment:
        return None

    marker = fragment.find("pako:")
    if marker == -1:
        return None

    payload = fragment[marker + len("pako:") :]
    for delimiter in (";", "&"):
        idx = payload.find(delimiter)
        if idx != -1:
            payload = payload[:idx]

    if not payload:
        raise InvalidNodeError("Mermaid URL is missing diagram payload")

    return _decode_mermaid_pako(payload)


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
            raise AssetMissingError(
                f"Unable to read Mermaid diagram '{resolved}'"
            ) from exc

    diagram = _extract_mermaid_live_diagram(src)
    if diagram is not None:
        return diagram, "url"

    return None


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
    asset_path = context.assets.latex_path(path)
    latex = formatter(
        path=asset_path,
        caption=caption,
        shortcaption=caption,
        label=label,
        width=width,
    )
    node = NavigableString(latex)
    node.processed = True
    return node


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
        node = NavigableString(placeholder)
        node.processed = True
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
        caption=effective_caption,
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
        node.processed = True
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

    raw_alt = element.get("alt")
    alt_text = raw_alt.strip() or None if raw_alt else None
    width = element.get("width") or None
    template = _figure_template_for(element)

    mermaid_payload = _load_mermaid_diagram(context, src)
    if mermaid_payload is not None:
        diagram, _ = mermaid_payload
        figure_node = _render_mermaid_diagram(
            context,
            diagram,
            template=template,
            caption=alt_text,
        )
        if figure_node is None:
            raise InvalidNodeError(
                f"Mermaid source '{src}' does not contain a valid diagram"
            )
        element.replace_with(figure_node)
        return

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
