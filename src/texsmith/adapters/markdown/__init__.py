"""Markdown conversion utilities for TeXSmith."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
import re
from threading import Lock
from typing import Any

import yaml


try:  # Optional dependency guard in case pymdownx is missing in constrained envs
    import pymdownx.superfences as _superfences
    from pymdownx.superfences import fence_code_format as _fence_code_format
except Exception:  # pragma: no cover - fallback when extension unavailable
    _fence_code_format = None
    _superfences = None


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
    "pymdownx.highlight",
    "pymdownx.superfences",
    "abbr",
    "admonition",
    "attr_list",
    "def_list",
    "footnotes",
    "texsmith.index:TexsmithIndexExtension",
    "texsmith.multi_citations:MultiCitationExtension",
    "texsmith.latex_raw:LatexRawExtension",
    "texsmith.missing_footnotes:MissingFootnotesExtension",
    "texsmith.latex_text:LatexTextExtension",
    "texsmith.smart_dashes:TexsmithSmartDashesExtension",
    "texsmith.smallcaps:SmallCapsExtension",
    "texsmith.mermaid:MermaidExtension",
    "texsmith.progressbar:ProgressBarExtension",
    "texsmith.quotes:TexsmithQuotesExtension",
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
    "pymdownx.inlinehilite",
    "pymdownx.keys",
    "pymdownx.magiclink",
    "pymdownx.mark",
    "pymdownx.saneheaders",
    "pymdownx.smartsymbols",
    "pymdownx.snippets",
    "pymdownx.tabbed",
    "pymdownx.tasklist",
    "pymdownx.tilde",
    "tables",
]


DEFAULT_EXTENSION_CONFIGS: dict[str, dict[str, object]] = {
    "pymdownx.keys": {
        "camel_case": True,
    },
    "pymdownx.highlight": {
        "anchor_linenums": True,
        "line_spans": "__span",
        "pygments_lang_class": True,
    },
    "pymdownx.superfences": {
        "custom_fences": (
            []
            if _fence_code_format is None
            else [
                {
                    "name": "mermaid",
                    "class": "mermaid",
                    "format": _fence_code_format,
                }
            ]
        )
    },
}


class MarkdownConversionError(Exception):
    """Raised when Markdown cannot be converted into HTML."""


@dataclass(slots=True)
class MarkdownDocument:
    """Result of converting Markdown into HTML."""

    html: str
    front_matter: dict[str, Any]


class _MarkdownCacheEntry:
    __slots__ = ("lock", "processor")

    def __init__(self, processor: Any) -> None:
        self.processor = processor
        self.lock = Lock()


_MARKDOWN_CACHE: dict[
    tuple[tuple[str, ...], tuple[str, ...]],
    _MarkdownCacheEntry,
] = {}
_MARKDOWN_CACHE_GUARD = Lock()


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
    *,
    base_path: str | Path | None = None,
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

    active_extensions = list(extensions or ())
    extensions_key = tuple(active_extensions)

    snippet_enabled = any(
        _normalise_extension_name(extension) == "pymdownx.snippets"
        for extension in active_extensions
    )
    snippet_paths: tuple[str, ...] = ()
    if snippet_enabled and base_path is not None:
        snippet_paths = (str(Path(base_path).resolve()),)

    entry = _resolve_markdown_entry(markdown, extensions_key, snippet_paths)

    resolved_base: Path | None = None
    if base_path is not None:
        try:
            resolved_base = Path(base_path).resolve()
        except OSError:
            resolved_base = Path(base_path)

    try:
        with entry.lock:
            processor = entry.processor
            reset_callback = getattr(processor, "reset", None)
            if callable(reset_callback):
                reset_callback()
            processor.texsmith_mermaid_base_path = (
                str(resolved_base) if resolved_base is not None else None
            )
            html = processor.convert(markdown_body)
    except MarkdownConversionError:
        raise
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


def _resolve_markdown_entry(
    markdown: Any,
    extensions_key: tuple[str, ...],
    snippet_paths: tuple[str, ...],
) -> _MarkdownCacheEntry:
    cache_key = (extensions_key, snippet_paths)
    entry = _MARKDOWN_CACHE.get(cache_key)
    if entry is not None:
        return entry
    with _MARKDOWN_CACHE_GUARD:
        entry = _MARKDOWN_CACHE.get(cache_key)
        if entry is None:
            processor = _build_markdown_processor(markdown, extensions_key, snippet_paths)
            entry = _MarkdownCacheEntry(processor)
            _MARKDOWN_CACHE[cache_key] = entry
    return entry


def _build_markdown_processor(
    markdown: Any,
    extensions_key: tuple[str, ...],
    snippet_paths: tuple[str, ...],
) -> Any:
    active_extensions = list(extensions_key)
    extension_configs = {
        name: dict(DEFAULT_EXTENSION_CONFIGS[name])
        for name in active_extensions
        if name in DEFAULT_EXTENSION_CONFIGS
    }
    snippet_enabled = any(
        _normalise_extension_name(extension) == "pymdownx.snippets"
        for extension in active_extensions
    )
    if snippet_enabled and snippet_paths:
        snippet_config = extension_configs.setdefault("pymdownx.snippets", {})
        existing_paths = _normalise_snippet_paths(snippet_config.get("base_path"))
        for path in snippet_paths:
            if path not in existing_paths:
                existing_paths.append(path)
        snippet_config["base_path"] = existing_paths
        snippet_config.setdefault("encoding", "utf-8")

    try:
        processor = markdown.Markdown(
            extensions=active_extensions, extension_configs=extension_configs
        )
    except Exception as exc:  # pragma: no cover - library-controlled
        raise MarkdownConversionError(f"Failed to initialize Markdown processor: {exc}") from exc

    return processor


def _normalise_extension_name(value: str | object) -> str:
    if not isinstance(value, str):
        return ""
    return value.split(":", 1)[0].lower()


def _normalise_snippet_paths(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    try:
        return [str(item) for item in value]  # type: ignore[arg-type]
    except TypeError:
        return [str(value)]
