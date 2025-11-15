"""Link handling utilities."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

from bs4.element import NavigableString, Tag
from requests.utils import requote_uri as requote_url

from texsmith.core.context import RenderContext
from texsmith.core.exceptions import AssetMissingError, InvalidNodeError
from texsmith.core.rules import RenderPhase, renders

from ..latex.utils import escape_latex_chars
from ._helpers import coerce_attribute, mark_processed, resolve_asset_path


def _coerce_existing_path(candidate: Path) -> Path | None:
    """Return a concrete file path for a directory or file candidate."""
    if candidate.is_file():
        return candidate.resolve()
    if candidate.is_dir():
        index_file = candidate / "index.md"
        if index_file.exists():
            return index_file.resolve()
    return None


def _iter_local_href_candidates(href: str) -> list[str]:
    """Return potential filesystem paths for a MkDocs-style link."""
    clean_href = href.split("#", 1)[0].split("?", 1)[0].strip()
    if not clean_href:
        return []

    candidates: list[str] = []

    def add_candidate(value: str | None) -> None:
        if value and value not in candidates:
            candidates.append(value)

    add_candidate(clean_href)

    trimmed = clean_href
    while trimmed.startswith("./"):
        trimmed = trimmed[2:]
    if trimmed.startswith("/"):
        trimmed = trimmed.lstrip("/")
    add_candidate(trimmed)

    if not trimmed:
        add_candidate("index.md")
        return candidates

    if trimmed.endswith("/"):
        stripped = trimmed.rstrip("/")
        add_candidate(stripped)
        add_candidate(f"{trimmed}index.md")
        if stripped:
            add_candidate(f"{stripped}/index.md")
            add_candidate(f"{stripped}.md")
    else:
        suffix = Path(trimmed).suffix
        if not suffix:
            add_candidate(f"{trimmed}.md")
            add_candidate(f"{trimmed}/index.md")

    return candidates


def _resolve_local_target(context: RenderContext, href: str) -> Path | None:
    runtime_dir = context.runtime.get("source_dir")
    if runtime_dir is not None:
        for candidate in _iter_local_href_candidates(href):
            candidate_path = _coerce_existing_path(Path(runtime_dir) / candidate)
            if candidate_path is not None:
                return candidate_path

    document_path = context.runtime.get("document_path")
    if document_path is not None:
        for candidate in _iter_local_href_candidates(href):
            resolved = resolve_asset_path(Path(document_path), candidate)
            if resolved is not None:
                coerced = _coerce_existing_path(resolved)
                if coerced is not None:
                    return coerced

    project_dir = getattr(context.config, "project_dir", None)
    if project_dir:
        for candidate in _iter_local_href_candidates(href):
            candidate_path = _coerce_existing_path(Path(project_dir) / candidate)
            if candidate_path is not None:
                return candidate_path

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
    identifier = coerce_attribute(element.get("identifier"))
    if not identifier:
        legacy_latex_accents = getattr(context.config, "legacy_latex_accents", False)
        literal = f"<{element.name}>"
        latex = escape_latex_chars(literal, legacy_accents=legacy_latex_accents)
        element.replace_with(mark_processed(NavigableString(latex)))
        return
    text = element.get_text(strip=False)

    latex = context.formatter.ref(text, ref=identifier)
    element.replace_with(mark_processed(NavigableString(latex)))


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
    identifier = coerce_attribute(element.get("data-autorefs-identifier"))
    if not identifier:
        return
    text = element.get_text(strip=False)

    latex = context.formatter.ref(text, ref=identifier)
    node = mark_processed(NavigableString(latex))
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


@renders("a", phase=RenderPhase.INLINE, priority=60, name="links", nestable=False)
def render_links(element: Tag, context: RenderContext) -> None:
    """Render hyperlinks and internal references."""
    href = coerce_attribute(element.get("href")) or ""
    element_id = coerce_attribute(element.get("id"))
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
        legacy_latex_accents = getattr(context.config, "legacy_latex_accents", False)
        latex = escape_latex_chars(text, legacy_accents=legacy_latex_accents)

    element.replace_with(mark_processed(NavigableString(latex)))
