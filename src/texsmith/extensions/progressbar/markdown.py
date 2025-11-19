"""Markdown extension transforming `[=80% "Label"]` blocks into progress bars."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import shlex
from xml.etree import ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor


PROGRESS_LINE = re.compile(
    r"""
    ^\s*
    \[=
    (?P<value>-?\d+(?:\.\d+)?)
    \s*%
    \s*
    (?:
        "(?P<label>[^"]*)"
    )?
    \]
    (?P<attrs>\{:[^}]+\})?
    \s*$
    """,
    re.VERBOSE,
)
ATTR_LINE = re.compile(r"^\s*\{:[^}]+\}\s*$")


@dataclass(slots=True)
class _AttributePayload:
    classes: list[str]
    identifier: str | None
    attributes: dict[str, str]


class _ProgressBarPreprocessor(Preprocessor):
    """Convert the Pymdown-like shorthand into semantic HTML."""

    def run(self, lines: list[str]) -> list[str]:  # type: ignore[override]
        result: list[str] = []
        index = 0
        length = len(lines)
        in_fence = False
        fence_char: str | None = None
        fence_len = 0

        while index < length:
            line = lines[index]
            stripped = line.lstrip()

            if not in_fence and self._looks_like_fence_start(stripped):
                fence_char = stripped[0]
                fence_len = self._fence_length(stripped)
                if fence_len >= 3:
                    in_fence = True
                result.append(line)
                index += 1
                continue

            if in_fence:
                result.append(line)
                if self._is_fence_end(stripped, fence_char, fence_len):
                    in_fence = False
                index += 1
                continue

            match = PROGRESS_LINE.match(line)
            attrs_text = None

            if match:
                attrs_text = match.group("attrs")
                if attrs_text is None and index + 1 < length:
                    next_candidate = lines[index + 1]
                    if ATTR_LINE.match(next_candidate):
                        attrs_text = next_candidate.strip()
                        index += 1

                payload = self._render_progressbar(match, attrs_text)
                result.append(payload)
                index += 1
                continue

            result.append(line)
            index += 1

        return result

    def _looks_like_fence_start(self, stripped: str) -> bool:
        if not stripped:
            return False
        char = stripped[0]
        if char not in {"`", "~"}:
            return False
        return stripped.startswith(char * 3)

    def _is_fence_end(
        self,
        stripped: str,
        fence_char: str | None,
        fence_len: int,
    ) -> bool:
        if not fence_char or fence_len < 3:
            return False
        return stripped.startswith(fence_char * fence_len)

    def _fence_length(self, stripped: str) -> int:
        if not stripped:
            return 0
        char = stripped[0]
        count = 0
        for ch in stripped:
            if ch == char:
                count += 1
            else:
                break
        return count

    def _render_progressbar(
        self,
        match: re.Match[str],
        attrs_text: str | None,
    ) -> str:
        percent = float(match.group("value"))
        percent = max(0.0, min(100.0, percent))
        label = match.group("label")
        if label is None or not label.strip():
            label = f"{percent:g}%"
        attrs = self._parse_attributes(attrs_text)

        classes = ["progress", _progress_bucket_class(percent), *attrs.classes]
        fraction = percent / 100.0
        fraction_str = _format_decimal(fraction, precision=4)

        container = ElementTree.Element("div")
        container.set("class", " ".join(filter(None, classes)))
        container.set("data-progress-percent", _format_decimal(percent, precision=2))
        container.set("data-progress-fraction", fraction_str)
        if attrs.identifier:
            container.set("id", attrs.identifier)
        for key, value in attrs.attributes.items():
            container.set(key, value)

        bar = ElementTree.SubElement(container, "div", {"class": "progress-bar"})
        bar.set("style", f"width:{_format_decimal(percent, precision=2)}%;")
        bar.set("data-progress-fraction", fraction_str)

        label_node = ElementTree.SubElement(bar, "p", {"class": "progress-label"})
        label_node.text = label

        return ElementTree.tostring(container, encoding="unicode")

    def _parse_attributes(self, raw: str | None) -> _AttributePayload:
        if not raw:
            return _AttributePayload([], None, {})
        body = raw.strip()
        if body.startswith("{"):
            body = body[2:-1].strip()

        classes: list[str] = []
        attributes: dict[str, str] = {}
        identifier: str | None = None

        lexer = shlex.shlex(body, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = ""

        for token in lexer:
            if not token:
                continue
            if token.startswith("."):
                classes.append(token[1:])
            elif token.startswith("#"):
                identifier = token[1:] or identifier
            elif "=" in token:
                key, value = token.split("=", 1)
                attributes[key] = value

        return _AttributePayload(classes, identifier, attributes)


def _progress_bucket_class(percent: float) -> str:
    bucket = int(math.floor(percent / 5.0) * 5)
    bucket = max(0, min(100, bucket))
    return f"progress-{bucket}plus"


def _format_decimal(value: float, *, precision: int) -> str:
    formatted = f"{value:.{precision}f}"
    return formatted.rstrip("0").rstrip(".") or "0"


class ProgressBarExtension(Extension):
    """Register the preprocessor on the Markdown pipeline."""

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802
        processor = _ProgressBarPreprocessor(md)
        md.preprocessors.register(processor, "texsmith_progressbar", 27)


def makeExtension(  # noqa: N802
    **kwargs: object,
) -> ProgressBarExtension:  # pragma: no cover - Markdown hook
    return ProgressBarExtension(**kwargs)


__all__ = ["ProgressBarExtension", "makeExtension"]
