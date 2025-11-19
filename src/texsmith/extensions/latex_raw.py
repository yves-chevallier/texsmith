"""Markdown extension adding support for raw LaTeX fence blocks and inline snippets."""

from __future__ import annotations

from html import escape
import re
from xml.etree import ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor
from markdown.preprocessors import Preprocessor


class _LatexRawPreprocessor(Preprocessor):
    """Transform custom `/// latex` fences into hidden HTML nodes."""

    _START_RE = re.compile(r"^\s*///\s+latex\s*$")
    _END_RE = re.compile(r"^\s*///\s*$")
    _FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")

    def run(self, lines: list[str]) -> list[str]:
        result: list[str] = []
        index = 0
        total = len(lines)
        in_fence = False
        fence_char: str | None = None
        fence_len = 0

        while index < total:
            line = lines[index]

            fence_match = self._FENCE_RE.match(line)
            if fence_match:
                fence_token = fence_match.group(1)
                token_char = fence_token[0]
                token_len = len(fence_token)
                if not in_fence:
                    in_fence = True
                    fence_char = token_char
                    fence_len = token_len
                else:
                    if token_char == fence_char and token_len >= fence_len:
                        in_fence = False
                        fence_char = None
                        fence_len = 0
                result.append(line)
                index += 1
                continue

            if in_fence:
                result.append(line)
                index += 1
                continue

            if not self._START_RE.match(line):
                result.append(line)
                index += 1
                continue

            start_index = index
            index += 1
            contents: list[str] = []

            while index < total and not self._END_RE.match(lines[index]):
                contents.append(lines[index])
                index += 1

            if index >= total:
                # No closing fence; fall back to raw lines
                result.extend(lines[start_index:])
                break

            escaped = escape("\n".join(contents), quote=False)
            result.append(f'<p class="latex-raw" style="display:none;">{escaped}</p>')
            index += 1  # Skip closing fence

        return result


class _LatexInlineProcessor(InlineProcessor):
    """Inline handler for ``{latex}[payload]`` markers."""

    def handleMatch(  # noqa: N802 - Markdown inline API requires camelCase
        self,
        match: re.Match[str],
        data: str,
    ) -> tuple[ElementTree.Element | None, int, int]:  # type: ignore[override]
        del data
        payload = match.group("payload")
        if payload is None:
            return None, match.start(0), match.end(0)

        element = ElementTree.Element("span")
        element.set("class", "latex-raw")
        element.set("style", "display:none;")
        element.text = escape(payload, quote=False)
        return element, match.start(0), match.end(0)


class LatexRawExtension(Extension):
    """Register the raw LaTeX block preprocessor."""

    def extendMarkdown(self, md: Markdown) -> None:  # type: ignore[override]  # noqa: N802
        md.preprocessors.register(_LatexRawPreprocessor(md), "texsmith_latex_raw", priority=27)
        pattern = r"\{latex\}\[(?P<payload>[^\]]+)\]"
        processor = _LatexInlineProcessor(pattern, md)
        md.inlinePatterns.register(processor, "texsmith_latex_inline", 181)


def makeExtension(**_: object) -> LatexRawExtension:  # pragma: no cover - API hook  # noqa: N802
    return LatexRawExtension()


__all__ = ["LatexRawExtension", "makeExtension"]
