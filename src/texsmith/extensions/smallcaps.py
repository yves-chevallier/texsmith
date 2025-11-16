"""Markdown extension that maps double underscores to small caps spans."""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor


_SMALL_CAPS_PATTERN = r"(?<!_)__(?!_)(.+?)__(?!_)"


class _SmallCapsInlineProcessor(InlineProcessor):
    """Inline processor converting ``__text__`` into a span marker."""

    def handleMatch(  # type: ignore[override]  # noqa: N802 - Markdown API requires camelCase
        self,
        match,  # type: ignore[override]  # noqa: ANN001
        data: str,
    ) -> tuple[ElementTree.Element | None, int | None, int | None]:
        content = match.group(1)
        if not content:
            return None, None, None

        element = ElementTree.Element("span", {"class": "texsmith-smallcaps"})
        parser = getattr(self, "parser", None)
        if parser is not None:
            parser.parseInline(element, content)
        else:  # pragma: no cover - parser is provided by Markdown
            element.text = content
        return element, match.start(0), match.end(0)


class SmallCapsExtension(Extension):
    """Register the ``__text__`` → ``<span class=\"texsmith-smallcaps\">`` processor."""

    def extendMarkdown(self, md: Markdown) -> None:  # type: ignore[override]  # noqa: N802
        processor = _SmallCapsInlineProcessor(_SMALL_CAPS_PATTERN, md)
        md.inlinePatterns.register(processor, "texsmith_smallcaps", 185)


def makeExtension(**_: object) -> SmallCapsExtension:  # pragma: no cover - API hook  # noqa: N802
    return SmallCapsExtension()


__all__ = ["SmallCapsExtension", "makeExtension"]
