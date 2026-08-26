"""Markdown extension converting straight double quotes into semantic ``<q>`` tags."""

from __future__ import annotations

import re
from re import Match
import xml.etree.ElementTree as ElementTree

from markdown import Extension, Markdown
from markdown.inlinepatterns import InlineProcessor


#: A brace group shaped like an ``attr_list`` payload — no ``}`` and no newline
#: inside, mirroring that extension's own ``BASE_RE``.
_BRACE_GROUP_RE = re.compile(r"\{:?[ ]*[^}\n ][^}\n]*[ ]*\}")

#: What tells an attribute list from a brace in running prose: an ``#id``, a
#: ``.class`` or a ``key=value`` token.
_ATTRIBUTE_TOKEN_RE = re.compile(r"(?:^|\s)(?:[.#]\S|[A-Za-z_:][\w.:-]*=)")


def _inside_attribute_list(data: str, start: int, end: int) -> bool:
    """Whether ``data[start:end]`` sits inside an ``attr_list`` brace group.

    Inline patterns run long before the ``attr_list`` treeprocessor, so turning
    ``width="50%"`` into a ``<q>`` element would split the brace group into
    three nodes and leave the whole thing as literal text — the attributes,
    including the ``id`` other references depend on, would silently vanish.
    """
    for group in _BRACE_GROUP_RE.finditer(data):
        if group.start() < start and end <= group.end():
            return bool(_ATTRIBUTE_TOKEN_RE.search(group.group(0)[1:-1]))
    return False


class _QuoteInlineProcessor(InlineProcessor):
    """Wrap straight double quotes in ``<q>`` elements."""

    def handleMatch(  # type: ignore[override]  # noqa: N802
        self,
        match: Match[str],
        data: str,
    ) -> tuple[ElementTree.Element | None, int | None, int | None]:
        if _inside_attribute_list(data, match.start(0), match.end(0)):
            # Decline the match: python-markdown then leaves the text alone.
            return None, None, None

        text = match.group(1)
        element = ElementTree.Element("q")
        element.text = text
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
