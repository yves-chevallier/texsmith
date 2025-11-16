"""Markdown extension that inlines Mermaid diagrams referenced via images."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

from ...core.exceptions import InvalidNodeError
from ..handlers._mermaid import (
    MERMAID_FILE_SUFFIXES,
    extract_mermaid_live_diagram,
    looks_like_mermaid,
)


class _MermaidImageTreeprocessor(Treeprocessor):
    """Replace standalone Mermaid image references with code blocks."""

    def run(self, root: ElementTree.Element) -> ElementTree.Element:  # type: ignore[override]
        base_path_value = getattr(self.md, "texsmith_mermaid_base_path", None)
        base_path = Path(base_path_value) if base_path_value else None

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
            diagram, source = diagram_payload

            caption = (image.get("alt") or image.get("title") or "").strip()
            body = self._apply_caption(diagram, caption)
            if not looks_like_mermaid(body):
                continue

            replacement = self._build_mermaid_block(body, link_href, source)
            self._replace_paragraph(parent_map.get(paragraph), paragraph, replacement)

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
    ) -> tuple[str, str] | None:
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
            return payload, str(resolved)

        try:
            diagram = extract_mermaid_live_diagram(cleaned)
        except InvalidNodeError:
            return None
        if diagram is not None:
            return diagram, source_hint

        return None

    def _resolve_path(self, src: str, base_path: Path | None) -> Path | None:
        candidate = Path(src)
        if not candidate.is_absolute():
            if base_path is None:
                return None
            candidate = (base_path / src).resolve()
        if not candidate.exists():
            return None
        return candidate

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

    def extendMarkdown(self, md: Markdown) -> None:  # type: ignore[override]  # noqa: N802
        processor = _MermaidImageTreeprocessor(md)
        md.treeprocessors.register(processor, "texsmith_mermaid_images", priority=15)


def makeExtension(**_: object) -> MermaidExtension:  # pragma: no cover - entry point  # noqa: N802
    return MermaidExtension()


__all__ = ["MermaidExtension", "makeExtension"]
