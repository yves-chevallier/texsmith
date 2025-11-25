"""Markdown extension converting straight double quotes into semantic ``<q>`` tags."""

from __future__ import annotations

from xml.etree import ElementTree as etree

from markdown import Extension
from markdown.inlinepatterns import InlineProcessor
from markdown.util import AtomicString


class _QuoteInlineProcessor(InlineProcessor):
    """Wrap straight double quotes in ``<q>`` elements."""

    def handleMatch(self, match, data):  # type: ignore[override]
        text = match.group(1)
        element = etree.Element("q")
        element.text = AtomicString(text)
        return element, match.start(0), match.end(0)


class TexsmithQuotesExtension(Extension):
    """Register the quote inline processor."""

    def extendMarkdown(self, md):  # type: ignore[override]
        pattern = r'(?<!\\)"([^"\n]+?)"'
        processor = _QuoteInlineProcessor(pattern, md)
        md.inlinePatterns.register(processor, "texsmith_quotes", 65)


def makeExtension(**kwargs):  # pragma: no cover - Markdown API hook
    return TexsmithQuotesExtension(**kwargs)


__all__ = ["TexsmithQuotesExtension", "makeExtension"]
