"""Markdown extension to stylize the literal ``LaTeX`` token inside paragraphs."""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor


_TARGET = "LaTeX"


class _LatexTextTreeprocessor(Treeprocessor):
    """Replace plain ``LaTeX`` occurrences with a styled HTML fragment."""

    def run(self, root: ElementTree.Element) -> None:  # type: ignore[override]
        for paragraph in root.iter("p"):
            self._process_element(paragraph)

    # -- internals -----------------------------------------------------
    def _process_element(self, element: ElementTree.Element) -> None:
        self._replace_text_node(element)
        for child in list(element):
            if self._is_code_element(child):
                if child.tail:
                    self._replace_tail(element, child)
                continue

            self._process_element(child)
            if child.tail:
                self._replace_tail(element, child)

    def _replace_text_node(self, element: ElementTree.Element) -> None:
        text = element.text
        if not text or _TARGET not in text:
            return

        parts = text.split(_TARGET)
        element.text = parts[0]
        for insert_pos, remainder in enumerate(parts[1:]):
            fragment = self._build_fragment()
            element.insert(insert_pos, fragment)
            if remainder:
                fragment.tail = remainder

    def _replace_tail(self, parent: ElementTree.Element, child: ElementTree.Element) -> None:
        tail = child.tail
        if not tail or _TARGET not in tail:
            return

        parts = tail.split(_TARGET)
        child.tail = parts[0]
        base_index = list(parent).index(child) + 1
        for offset, remainder in enumerate(parts[1:]):
            fragment = self._build_fragment()
            parent.insert(base_index + offset, fragment)
            if remainder:
                fragment.tail = remainder

    def _is_code_element(self, element: ElementTree.Element) -> bool:
        tag = element.tag
        if isinstance(tag, str):
            tag = tag.lower()
        return tag in {"code", "pre"}

    def _build_fragment(self) -> ElementTree.Element:
        outer = ElementTree.Element(
            "span",
            {
                "class": "latex-text",
                "style": "font-family: 'Times New Roman', serif;",
            },
        )
        outer.text = "L"

        lowered_a = ElementTree.SubElement(
            outer,
            "span",
            {"style": ("position: relative; top: 0.2em; left: -0.05em; font-size: 0.9em;")},
        )
        lowered_a.text = "a"
        lowered_a.tail = "T"

        small_caps_e = ElementTree.SubElement(
            outer,
            "span",
            {
                "style": "font-variant: small-caps;",
            },
        )
        small_caps_e.text = "e"

        ElementTree.SubElement(
            outer,
            "span",
            {
                "style": "font-variant: small-caps; letter-spacing: -0.05em;",
            },
        ).text = "X"

        return outer


class LatexTextExtension(Extension):
    """Register the ``LaTeX`` paragraph replacement processor."""

    def extendMarkdown(self, md: Markdown) -> None:  # type: ignore[override]  # noqa: N802
        md.treeprocessors.register(_LatexTextTreeprocessor(md), "texsmith_latex_text", priority=15)


def makeExtension(**_: object) -> LatexTextExtension:  # pragma: no cover - API hook  # noqa: N802
    return LatexTextExtension()


__all__ = ["LatexTextExtension", "makeExtension"]
