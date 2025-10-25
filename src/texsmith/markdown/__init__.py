"""Markdown conversion utilities for TeXSmith."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import re
from typing import Any

import yaml


__all__ = [
    "DEFAULT_MARKDOWN_EXTENSIONS",
    "MarkdownConversionError",
    "MarkdownDocument",
    "deduplicate_markdown_extensions",
    "normalize_markdown_extensions",
    "render_markdown",
    "resolve_markdown_extensions",
    "split_front_matter",
]


DEFAULT_MARKDOWN_EXTENSIONS = [
    "abbr",
    "admonition",
    "attr_list",
    "def_list",
    "footnotes",
    "texsmith.markdown_extensions.missing_footnotes:MissingFootnotesExtension",
    "md_in_html",
    "mdx_math",
    "pymdownx.betterem",
    "pymdownx.blocks.caption",
    "pymdownx.blocks.html",
    "pymdownx.caret",
    "pymdownx.critic",
    "pymdownx.details",
    "pymdownx.emoji",
    "pymdownx.fancylists",
    "pymdownx.highlight",
    "pymdownx.inlinehilite",
    "pymdownx.keys",
    "pymdownx.magiclink",
    "pymdownx.mark",
    "pymdownx.saneheaders",
    "pymdownx.smartsymbols",
    "pymdownx.snippets",
    "pymdownx.superfences",
    "pymdownx.tabbed",
    "pymdownx.tasklist",
    "pymdownx.tilde",
    "tables",
    "toc",
]


class MarkdownConversionError(Exception):
    """Raised when Markdown cannot be converted into HTML."""


@dataclass(slots=True)
class MarkdownDocument:
    """Result of converting Markdown into HTML."""

    html: str
    front_matter: dict[str, Any]


def resolve_markdown_extensions(
    requested: Iterable[str] | None,
    disabled: Iterable[str] | None,
) -> list[str]:
    """Return the active Markdown extension list after applying overrides."""
    enabled = normalize_markdown_extensions(requested)
    disabled_normalized = {
        extension.lower() for extension in normalize_markdown_extensions(disabled)
    }

    combined = deduplicate_markdown_extensions(list(DEFAULT_MARKDOWN_EXTENSIONS) + enabled)

    if not disabled_normalized:
        return combined

    return [extension for extension in combined if extension.lower() not in disabled_normalized]


def deduplicate_markdown_extensions(values: Iterable[str]) -> list[str]:
    """Remove duplicate extensions while preserving order and case."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def normalize_markdown_extensions(
    values: Iterable[str] | str | None,
) -> list[str]:
    """Normalise extension names from CLI-friendly strings into a flat list."""
    if values is None:
        return []

    if isinstance(values, str):
        candidates: Iterable[str] = [values]
    else:
        candidates = values

    normalized: list[str] = []
    for value in candidates:
        if not isinstance(value, str):
            continue
        chunks = re.split(r"[,\s\x00]+", value)
        normalized.extend(chunk for chunk in chunks if chunk)
    return normalized


def render_markdown(
    source: str,
    extensions: Sequence[str] | None = None,
) -> MarkdownDocument:
    """Convert Markdown source into HTML while collecting front matter."""
    try:
        import markdown
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise MarkdownConversionError(
            "Python Markdown is required to process Markdown inputs; "
            "install the 'markdown' package."
        ) from exc

    metadata, markdown_body = split_front_matter(source)

    try:
        md = markdown.Markdown(extensions=list(extensions or ()))
    except Exception as exc:  # pragma: no cover - library-controlled
        raise MarkdownConversionError(f"Failed to initialize Markdown processor: {exc}") from exc

    try:
        html = md.convert(markdown_body)
    except Exception as exc:  # pragma: no cover - library-controlled
        raise MarkdownConversionError(f"Failed to convert Markdown source: {exc}") from exc

    return MarkdownDocument(html=html, front_matter=metadata)


def split_front_matter(source: str) -> tuple[dict[str, Any], str]:
    """Split YAML front matter from Markdown content, returning metadata and body."""
    candidate = source.lstrip("\ufeff")
    prefix_len = len(source) - len(candidate)
    lines = candidate.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, source

    front_matter_lines: list[str] = []
    closing_index: int | None = None
    for idx, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped in {"---", "..."}:
            closing_index = idx
            break
        front_matter_lines.append(line)

    if closing_index is None:
        return {}, source

    raw_block = "\n".join(front_matter_lines)
    try:
        metadata = yaml.safe_load(raw_block) or {}
    except yaml.YAMLError:
        return {}, source

    if not isinstance(metadata, dict):
        metadata = {}

    body_lines = lines[closing_index + 1 :]
    body = "\n".join(body_lines)
    if source.endswith("\n"):
        body += "\n"

    prefix = source[:prefix_len]
    return metadata, prefix + body
