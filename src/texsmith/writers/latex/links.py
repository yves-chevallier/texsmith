"""Local link-target resolution helpers used by the LaTeX writer.

These resolve MkDocs-style relative links to concrete source files and infer a
heading anchor for cross references. They are invoked lazily from
:mod:`texsmith.writers.latex.writer` through a duck-typed render context.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from texsmith.adapters.html_utils import coerce_attribute, resolve_asset_path
from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.context import RenderContextLike


def _coerce_existing_path(candidate: Path) -> Path | None:
    """Return a concrete file path for a directory or file candidate."""
    if candidate.is_file():
        return candidate.resolve()
    if candidate.is_dir():
        index_file = candidate / "index.md"
        if index_file.exists():
            return index_file.resolve()
        html_index = candidate / "index.html"
        if html_index.exists():
            return html_index.resolve()
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
        add_candidate(f"{trimmed}index.html")
        if stripped:
            add_candidate(f"{stripped}/index.md")
            add_candidate(f"{stripped}/index.html")
            add_candidate(f"{stripped}.md")
            add_candidate(f"{stripped}.html")
    else:
        suffix = Path(trimmed).suffix
        if not suffix:
            add_candidate(f"{trimmed}.md")
            add_candidate(f"{trimmed}.html")
            add_candidate(f"{trimmed}/index.md")
            add_candidate(f"{trimmed}/index.html")

    return candidates


def _resolve_local_target(context: RenderContextLike, href: str) -> Path | None:
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


_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
_HTML_EXTENSIONS = {".html", ".htm"}
_MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mkd", ".mkdn"}


@lru_cache(maxsize=256)
def _extract_primary_heading(path: str) -> str | None:
    candidate = Path(path)
    suffix = candidate.suffix.lower()
    try:
        payload = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    if suffix in _HTML_EXTENSIONS:
        soup = BeautifulSoup(payload, "html.parser")
    elif suffix in _MARKDOWN_EXTENSIONS:
        document = render_markdown(
            payload,
            extensions=DEFAULT_MARKDOWN_EXTENSIONS,
            base_path=candidate.parent,
        )
        soup = BeautifulSoup(document.html, "html.parser")
    else:
        return None

    heading = soup.find(_HEADING_TAGS, id=True)
    if heading is None:
        return None
    return coerce_attribute(heading.get("id")) or None


def _infer_heading_reference(path: Path) -> str | None:
    reference = _extract_primary_heading(str(path.resolve()))
    return reference
