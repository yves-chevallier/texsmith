"""Markdown extension providing the ``#[term]`` hashtag syntax."""

from __future__ import annotations

import re
from xml.etree import ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor


TAG_PATTERN = re.compile(r"\[([^\]]+)\]")
STYLE_PATTERN = re.compile(r"\{([^}]+)\}")


class _IndexInlineProcessor(InlineProcessor):
    """Replace index syntax with tagged spans."""

    def handleMatch(  # noqa: N802 - Markdown inline API requires camelCase
        self,
        match: re.Match[str],
        data: str,
    ) -> tuple[ElementTree.Element, int, int]:  # type: ignore[override]
        del data
        payload = match.group("payload")
        registry = match.group("registry1")
        style_token = match.group("style")

        tags = _extract_tags(payload)
        if not tags:
            return None, match.start(0), match.end(0)

        element = ElementTree.Element("span")
        element.set("class", "ts-hashtag")
        for index, tag in enumerate(tags):
            key = "data-tag" if index == 0 else f"data-tag{index}"
            element.set(key, tag)

        normalised_style = _normalise_style(style_token)
        if normalised_style:
            element.set("data-style", normalised_style)

        if registry:
            element.set("data-registry", registry)

        # The index marker is invisible in the output text
        element.text = ""
        return element, match.start(0), match.end(0)


def _extract_tags(payload: str | None) -> list[str]:
    if not payload:
        return []
    values = [part.strip() for part in TAG_PATTERN.findall(payload)]
    return [value for value in values if value]


def _normalise_style(style_token: str | None) -> str | None:
    if not style_token:
        return None
    match = STYLE_PATTERN.search(style_token)
    if not match:
        return None
    style = match.group(1).strip().lower()
    if not style:
        return None
    if style == "ib":
        style = "bi"
    if style not in {"b", "i", "bi"}:
        return None
    return style


class TexsmithIndexExtension(Extension):
    """Register the inline index processor with Python-Markdown."""

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802
        """Match modern and legacy index syntaxes and register the inline processor."""
        pattern = (
            r"(?<!\\)"
            r"(?P<prefix>#|\{index(?::(?P<registry1>[^\]\{\(\s]+))?\}|%)"
            r"(?P<payload>(?:\[[^\]]+\])+)"
            r"(?P<style>\{[^}]+\})?"
        )
        processor = _IndexInlineProcessor(pattern, md)
        md.inlinePatterns.register(processor, "texsmith_index", 180)


def makeExtension(**kwargs: object) -> TexsmithIndexExtension:  # noqa: N802 - Markdown API hook; pragma: no cover
    return TexsmithIndexExtension(**kwargs)


__all__ = ["TexsmithIndexExtension", "makeExtension"]
