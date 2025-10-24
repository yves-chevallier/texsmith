"""Link handling utilities."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

from bs4 import NavigableString, Tag
from requests.utils import requote_uri as requote_url

from ..context import RenderContext
from ..exceptions import AssetMissingError, InvalidNodeError
from ..rules import RenderPhase, renders
from ..utils import escape_latex_chars, resolve_asset_path


def _resolve_local_target(context: RenderContext, href: str) -> Path | None:
    runtime_dir = context.runtime.get("source_dir")
    if runtime_dir is not None:
        candidate = Path(runtime_dir) / href
        if candidate.exists():
            return candidate.resolve()

    document_path = context.runtime.get("document_path")
    if document_path is not None:
        resolved = resolve_asset_path(Path(document_path), href)
        if resolved is not None:
            return resolved

    project_dir = getattr(context.config, "project_dir", None)
    if project_dir:
        candidate = Path(project_dir) / href
        if candidate.exists():
            return candidate.resolve()

    return None


@renders(
    "autoref",
    phase=RenderPhase.INLINE,
    priority=10,
    name="autoref_tags",
    nestable=False,
)
def render_autoref(element: Tag, context: RenderContext) -> None:
    """Render <autoref> custom tags."""
    identifier = element.get("identifier")
    if not identifier:
        raise InvalidNodeError("autoref tag missing identifier attribute")
    text = element.get_text(strip=False)

    latex = context.formatter.ref(text, ref=identifier)
    node = NavigableString(latex)
    node.processed = True
    element.replace_with(node)


@renders(
    "span",
    phase=RenderPhase.INLINE,
    priority=15,
    name="autoref_spans",
    nestable=False,
    auto_mark=False,
)
def render_autoref_spans(element: Tag, context: RenderContext) -> None:
    """Render MkDocs autoref span placeholders."""
    identifier = element.get("data-autorefs-identifier")
    if not identifier:
        return
    text = element.get_text(strip=False)

    latex = context.formatter.ref(text, ref=identifier)
    node = NavigableString(latex)
    node.processed = True
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


@renders("a", phase=RenderPhase.INLINE, priority=60, name="links", nestable=False)
def render_links(element: Tag, context: RenderContext) -> None:
    """Render hyperlinks and internal references."""
    href_attr = element.get("href")
    href = href_attr if isinstance(href_attr, str) else ""
    element_id = element.get("id")
    text = element.get_text(strip=False)

    # Already handled in preprocessing modules
    if element.name != "a":
        return

    parsed_href = urlparse(href)
    scheme = (parsed_href.scheme or "").lower()

    if scheme in {"http", "https"}:
        latex = context.formatter.href(text=text, url=requote_url(href))
    elif scheme:
        raise InvalidNodeError(f"Unsupported link scheme '{scheme}' for '{href}'.")
    elif href.startswith("#"):
        latex = context.formatter.ref(text, ref=href[1:])
    elif href == "" and element_id:
        latex = context.formatter.label(element_id)
    elif href:
        resolved = _resolve_local_target(context, href)
        if resolved is None:
            raise AssetMissingError(f"Unable to resolve link target '{href}'")
        content = resolved.read_bytes()
        digest = sha256(content).hexdigest()
        reference = f"snippet:{digest}"
        context.state.register_snippet(
            reference,
            {
                "path": resolved,
                "content": content,
                "format": resolved.suffix[1:] if resolved.suffix else "",
            },
        )
        latex = context.formatter.ref(text or "extrait", ref=reference)
    else:
        latex = escape_latex_chars(text)

    node = NavigableString(latex)
    node.processed = True
    element.replace_with(node)
