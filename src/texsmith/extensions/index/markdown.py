"""Markdown extension introducing the ``#[tag]`` inline index syntax."""

from __future__ import annotations

import re
from xml.etree import ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor


TAG_PATTERN = re.compile(r"\[([^\]]+)\]")
STYLE_PATTERN = re.compile(r"^[ibIB]{1,2}$")


class _HashtagInlineProcessor(InlineProcessor):
    """Replace hash-tag syntax with tagged spans."""

    def handleMatch(  # noqa: N802 - Markdown inline API requires camelCase
        self,
        match: re.Match[str],
        data: str,
    ) -> tuple[ElementTree.Element, int, int]:  # type: ignore[override]
        del data
        tags = _extract_tags(match.group("payload"))
        style = _normalise_style(match.group("style"))

        element = ElementTree.Element("span")
        element.set("class", "ts-hashtag")
        for index, tag in enumerate(tags):
            key = "data-tag" if index == 0 else f"data-tag{index}"
            element.set(key, tag)
        if style:
            element.set("data-style", style)
        element.text = tags[0]
        return element, match.start(0), match.end(0)


def _extract_tags(payload: str | None) -> list[str]:
    if not payload:
        return ["index"]
    values = [part.strip() for part in TAG_PATTERN.findall(payload)]
    filtered = [value for value in values if value]
    if not filtered:
        return ["index"]
    return filtered[:3]


def _normalise_style(token: str | None) -> str:
    if not token:
        return ""
    stripped = token.strip("{}").lower()
    if not stripped or not STYLE_PATTERN.match(stripped):
        return ""
    # Deduplicate while preserving order (e.g. "bi" vs "ib")
    result: list[str] = []
    for char in stripped:
        if char not in result:
            result.append(char)
    return "".join(result)


class TexsmithIndexExtension(Extension):
    """Register the inline hashtag processor with Python-Markdown."""

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802
        pattern = r"#(?P<payload>(?:\[[^\]]+\]){1,3})(?P<style>\{[ibIB]{1,2}\})?"
        processor = _HashtagInlineProcessor(pattern, md)
        md.inlinePatterns.register(processor, "texsmith_index_hashtag", 180)


def makeExtension(**kwargs: object) -> TexsmithIndexExtension:  # noqa: N802 - Markdown API hook; pragma: no cover
    return TexsmithIndexExtension(**kwargs)


__all__ = ["TexsmithIndexExtension", "makeExtension"]
