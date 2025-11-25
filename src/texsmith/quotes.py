"""Markdown extension converting straight double quotes into semantic ``<q>`` tags."""

from __future__ import annotations

from re import Match
import xml.etree.ElementTree as ElementTree

from markdown import Extension, Markdown
from markdown.inlinepatterns import InlineProcessor
from markdown.util import AtomicString


class _QuoteInlineProcessor(InlineProcessor):
    """Wrap straight double quotes in ``<q>`` elements."""

    def handleMatch(  # type: ignore[override]  # noqa: N802
        self,
        match: Match[str],
        data: str,
    ) -> tuple[ElementTree.Element, int, int]:
        text = match.group(1)
        element = ElementTree.Element("q")
        element.text = AtomicString(text)
        return element, match.start(0), match.end(0)


class TexsmithQuotesExtension(Extension):
    """Register the quote inline processor."""

    def extendMarkdown(self, md: Markdown) -> None:  # type: ignore[override]  # noqa: N802
        pattern = r'(?<!\\)"([^"\n]+?)"'
        processor = _QuoteInlineProcessor(pattern, md)
        md.inlinePatterns.register(processor, "texsmith_quotes", 65)


def makeExtension(**kwargs: object) -> TexsmithQuotesExtension:  # noqa: N802
    return TexsmithQuotesExtension(**kwargs)


__all__ = ["TexsmithQuotesExtension", "makeExtension"]
