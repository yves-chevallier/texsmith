"""Markdown extension that converts invisible Unicode characters into NBSP."""

from __future__ import annotations

from typing import ClassVar
import xml.etree.ElementTree as ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor


# Invisible / format-only characters that copy-paste sources frequently smuggle
# into Markdown text and that small-caps fonts (e.g. ``lmromancaps10-regular``
# used by biblatex+babel-french bibliographies) typically lack a glyph for,
# producing "Missing character" warnings during XeLaTeX runs.
_INVISIBLE_CHARS = (
    "​"  # ZERO WIDTH SPACE
    "‌"  # ZERO WIDTH NON-JOINER
    "‍"  # ZERO WIDTH JOINER
    "﻿"  # ZERO WIDTH NO-BREAK SPACE / BOM
)
_TRANSLATION_TABLE = {ord(ch): " " for ch in _INVISIBLE_CHARS}


def _normalise(text: str) -> str:
    return text.translate(_TRANSLATION_TABLE)


class _InvisibleCharsTreeprocessor(Treeprocessor):
    """Replace stray zero-width characters with a non-breaking space."""

    _SKIP_TAGS: ClassVar[set[str]] = {"code", "pre", "kbd", "script", "style"}

    def run(self, root: ElementTree.Element) -> None:  # type: ignore[override]
        self._process(root)

    def _process(self, element: ElementTree.Element) -> None:
        if self._is_skipped(element):
            return

        if element.text:
            element.text = _normalise(element.text)

        for child in list(element):
            self._process(child)
            if child.tail:
                child.tail = _normalise(child.tail)

    def _is_skipped(self, element: ElementTree.Element) -> bool:
        tag = element.tag
        if isinstance(tag, str):
            tag = tag.lower()
        return tag in self._SKIP_TAGS


class InvisibleCharsExtension(Extension):
    """Register the invisible-character normaliser tree-processor."""

    def extendMarkdown(self, md: Markdown) -> None:  # type: ignore[override]  # noqa: N802
        md.treeprocessors.register(
            _InvisibleCharsTreeprocessor(md), "texsmith_invisible_chars", priority=15
        )


def makeExtension(**_: object) -> InvisibleCharsExtension:  # pragma: no cover - API hook  # noqa: N802
    return InvisibleCharsExtension()


__all__ = ["InvisibleCharsExtension", "makeExtension"]
