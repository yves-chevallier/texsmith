"""Markdown extension that inlines Mermaid diagrams referenced via images."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
import xml.etree.ElementTree as ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

from ..adapters.handlers._mermaid import (
    MERMAID_FILE_SUFFIXES,
    extract_mermaid_live_diagram,
    looks_like_mermaid,
)
from ..core.exceptions import InvalidNodeError


def _collapse_relative_path(src: str) -> str:
    """Return a relative path with ``..`` segments normalised away."""
    if not src or src.startswith(("/", "\\")):
        return src

    segments: list[str] = []
    for segment in src.split("/"):
        if not segment or segment == ".":
            continue
        if segment == "..":
            if segments:
                segments.pop()
            continue
        segments.append(segment)
    return "/".join(segments)


class _MermaidImageTreeprocessor(Treeprocessor):
    """Replace standalone Mermaid image references with code blocks."""

    def __init__(
        self,
        md: Markdown,
        *,
        extra_base_paths: Sequence[Path] | None = None,
    ) -> None:
        super().__init__(md)
        self._extra_base_paths = [path for path in (extra_base_paths or []) if path]

    def run(self, root: ElementTree.Element) -> ElementTree.Element:  # type: ignore[override]
        base_path_value = getattr(self.md, "texsmith_mermaid_base_path", None)
        base_path: Path | None = None
        if base_path_value:
            try:
                base_path = Path(base_path_value).resolve()
            except OSError:
                base_path = Path(base_path_value)

        parent_map: dict[ElementTree.Element, ElementTree.Element] = {}
        for parent in root.iter():
            for child in list(parent):
                parent_map[child] = parent

        for paragraph in list(root.iter("p")):
            image, link_href = self._extract_image(paragraph)
            if image is None:
                continue

            diagram_payload = self._load_diagram(image, base_path)
            if diagram_payload is None:
                continue
            diagram, source, trusted = diagram_payload

            caption = (image.get("alt") or image.get("title") or "").strip()
            body = self._apply_caption(diagram, caption)
            if not trusted and not looks_like_mermaid(body):
                continue

            replacement = self._build_mermaid_block(body, link_href, source)
            wrapper = self._wrap_with_link(replacement, link_href)
            self._replace_paragraph(parent_map.get(paragraph), paragraph, wrapper)

        return root

    def _extract_image(
        self, paragraph: ElementTree.Element
    ) -> tuple[ElementTree.Element | None, str | None]:
        if any((node.tail or "").strip() for node in paragraph):
            return None, None
        paragraph_text = (paragraph.text or "").strip()
        if paragraph_text:
            return None, None
        if len(paragraph) != 1:
            return None, None

        node = paragraph[0]
        if node.tag == "img":
            if (node.tail or "").strip():
                return None, None
            return node, None

        if node.tag == "a" and len(node) == 1 and node[0].tag == "img":
            image = node[0]
            if (node.text or "").strip() or (image.tail or "").strip():
                return None, None
            href = node.get("href")
            return image, href

        return None, None

    def _load_diagram(
        self,
        image: ElementTree.Element,
        base_path: Path | None,
    ) -> tuple[str, str, bool] | None:
        raw_src = image.get("src")
        if not raw_src:
            return None

        cleaned = raw_src.replace("\n", "").replace("\r", "").strip()
        if not cleaned:
            return None

        source_hint = cleaned
        simplified = cleaned.split("?", 1)[0].split("#", 1)[0].lower()
        if simplified.endswith(MERMAID_FILE_SUFFIXES):
            if cleaned.startswith(("http://", "https://")):
                return None
            resolved = self._resolve_path(cleaned, base_path)
            if resolved is None:
                return None
            try:
                payload = resolved.read_text(encoding="utf-8")
            except OSError:
                return None
            return payload, str(resolved), True

        try:
            diagram = extract_mermaid_live_diagram(cleaned)
        except InvalidNodeError:
            return None
        if diagram is not None:
            return diagram, source_hint, False

        return None

    def _resolve_path(self, src: str, base_path: Path | None) -> Path | None:
        normalised = _collapse_relative_path(src.replace("\\", "/"))
        candidate = Path(normalised)
        if candidate.is_absolute():
            return candidate if candidate.exists() else None

        search_roots: list[Path] = []
        if base_path is not None:
            search_roots.append(base_path)
        for fallback in self._extra_base_paths:
            if fallback not in search_roots:
                search_roots.append(fallback)

        for root in search_roots:
            resolved = (root / normalised).resolve()
            if resolved.exists():
                return resolved
        return None

    def _apply_caption(self, diagram: str, caption: str) -> str:
        if not caption:
            return diagram

        meaningful_line = None
        for line in diagram.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            meaningful_line = stripped
            break

        if meaningful_line and meaningful_line.startswith("%%"):
            return diagram

        sanitized = caption.strip()
        if not sanitized:
            return diagram

        body = diagram.lstrip("\ufeff")
        return f"%% {sanitized}\n{body}"

    def _build_mermaid_block(
        self,
        diagram: str,
        link_href: str | None,
        source_hint: str,
    ) -> ElementTree.Element:
        pre = ElementTree.Element("pre", {"class": "mermaid"})
        if link_href:
            pre.set("data-mermaid-link", link_href)
        if source_hint:
            pre.set("data-mermaid-source", source_hint)
        pre.text = diagram
        return pre

    def _wrap_with_link(
        self,
        node: ElementTree.Element,
        link_href: str | None,
    ) -> ElementTree.Element:
        if not link_href:
            return node

        anchor = ElementTree.Element("a", {"href": link_href})
        anchor.append(node)
        return anchor

    def _replace_paragraph(
        self,
        parent: ElementTree.Element | None,
        paragraph: ElementTree.Element,
        replacement: ElementTree.Element,
    ) -> None:
        replacement.tail = paragraph.tail
        if parent is None:
            return
        for index, child in enumerate(list(parent)):
            if child is paragraph:
                parent.insert(index, replacement)
                parent.remove(paragraph)
                return


class MermaidExtension(Extension):
    """Register the Mermaid image treeprocessor."""

    def __init__(self, **kwargs: object) -> None:
        self.config = {
            "base_paths": [(), "Additional directories searched for Mermaid files."],
        }
        super().__init__(**kwargs)

    @staticmethod
    def _coerce_paths(paths: Iterable[object]) -> list[Path]:
        resolved: list[Path] = []
        for entry in paths:
            if entry is None:
                continue
            try:
                candidate = Path(entry).expanduser()
            except TypeError:
                continue
            try:
                resolved.append(candidate.resolve())
            except OSError:
                resolved.append(candidate)
        return resolved

    def extendMarkdown(self, md: Markdown) -> None:  # type: ignore[override]  # noqa: N802
        extra_paths = self._coerce_paths(self.getConfig("base_paths") or ())
        processor = _MermaidImageTreeprocessor(md, extra_base_paths=extra_paths)
        md.treeprocessors.register(processor, "texsmith_mermaid_images", priority=15)


def makeExtension(  # noqa: N802 - Markdown expects this entry point name
    **kwargs: object,
) -> MermaidExtension:  # pragma: no cover - entry point
    return MermaidExtension(**kwargs)


__all__ = ["MermaidExtension", "makeExtension"]
