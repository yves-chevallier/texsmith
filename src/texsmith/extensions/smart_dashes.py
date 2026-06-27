"""Markdown extension that converts ``--``/``---`` into proper dashes."""

from __future__ import annotations

import re
from typing import ClassVar
import xml.etree.ElementTree as ElementTree

from markdown import Extension, Markdown
from markdown.treeprocessors import Treeprocessor


_DASH_PATTERN = re.compile(r"---|--")


def _replace_dashes(text: str) -> str:
    """Replace ASCII dash sequences with typographic counterparts."""

    def _swap(match: re.Match[str]) -> str:
        payload = match.group(0)
        return "\u2014" if payload == "---" else "\u2013"

    return _DASH_PATTERN.sub(_swap, text)


class _SmartDashesTreeprocessor(Treeprocessor):
    """Replace double/triple hyphens outside code with typographic dashes."""

    _SKIP_TAGS: ClassVar[set[str]] = {"code", "pre", "kbd", "script", "style"}

    def run(self, root: ElementTree.Element) -> None:  # type: ignore[override]
        self._process(root)

    def _process(self, element: ElementTree.Element) -> None:
        if self._is_skipped(element):
            return

        if element.text:
            element.text = _replace_dashes(element.text)

        for child in list(element):
            self._process(child)
            if child.tail:
                child.tail = _replace_dashes(child.tail)

    def _is_skipped(self, element: ElementTree.Element) -> bool:
        tag = element.tag
        if isinstance(tag, str):
            tag = tag.lower()
        return tag in self._SKIP_TAGS


class TexsmithSmartDashesExtension(Extension):
    """Register the smart dash tree-processor."""

    def extendMarkdown(self, md: Markdown) -> None:  # type: ignore[override]  # noqa: N802
        md.treeprocessors.register(
            _SmartDashesTreeprocessor(md), "texsmith_smart_dashes", priority=16
        )


def makeExtension(**kwargs: object) -> TexsmithSmartDashesExtension:  # noqa: N802
    return TexsmithSmartDashesExtension(**kwargs)


__all__ = ["TexsmithSmartDashesExtension", "makeExtension"]
