"""Markdown extension that replaces TeX logo keywords with semantic HTML."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
import re
import xml.etree.ElementTree as ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

from .specs import LogoSpec, alias_mapping


class _TexLogosTreeprocessor(Treeprocessor):
    """Replace textual tokens with spans that carry TeX logo metadata."""

    def __init__(self, md: Markdown) -> None:
        super().__init__(md)
        self._alias_map = alias_mapping()
        self._pattern = _compile_pattern(self._alias_map)

    def run(self, root: ElementTree.Element) -> None:  # type: ignore[override]
        self._process_element(root)

    # -- recursive traversal -------------------------------------------------
    def _process_element(self, element: ElementTree.Element) -> None:
        if self._is_logo_container(element):
            return

        if self._is_code_element(element):
            for child in list(element):
                if child.tail:
                    self._replace_tail(element, child)
            return

        self._replace_text_node(element)

        for child in list(element):
            self._process_element(child)
            if child.tail:
                self._replace_tail(element, child)

    def _replace_text_node(self, element: ElementTree.Element) -> None:
        text = element.text
        if not text:
            return

        segments = list(self._split_segments(text))
        if not any(isinstance(part, LogoSpec) for part in segments):
            return

        element.text = ""
        insert_pos = 0
        last_fragment: ElementTree.Element | None = None
        for part in segments:
            if isinstance(part, str):
                if last_fragment is None:
                    element.text += part
                else:
                    last_fragment.tail = (last_fragment.tail or "") + part
                continue

            fragment = self._build_fragment(part)
            element.insert(insert_pos, fragment)
            insert_pos += 1
            last_fragment = fragment

    def _replace_tail(self, parent: ElementTree.Element, child: ElementTree.Element) -> None:
        tail = child.tail
        if not tail:
            return

        segments = list(self._split_segments(tail))
        if not any(isinstance(part, LogoSpec) for part in segments):
            return

        child.tail = ""
        insert_pos = list(parent).index(child) + 1
        last_fragment: ElementTree.Element | None = None
        for part in segments:
            if isinstance(part, str):
                if last_fragment is None:
                    child.tail += part
                else:
                    last_fragment.tail = (last_fragment.tail or "") + part
                continue

            fragment = self._build_fragment(part)
            parent.insert(insert_pos, fragment)
            insert_pos += 1
            last_fragment = fragment

    # -- helpers -------------------------------------------------------------
    def _split_segments(self, value: str) -> Iterator[str | LogoSpec]:
        cursor = 0
        for match in self._pattern.finditer(value):
            start, end = match.span()
            if start > cursor:
                yield value[cursor:start]
            alias = match.group(0)
            spec = self._alias_map.get(alias)
            if (start > 0 and value[start - 1].isalnum()) or (
                end < len(value) and value[end].isalnum()
            ):
                yield value[start:end]
            elif spec:
                yield spec
            else:  # pragma: no cover - defensive
                yield alias
            cursor = end
        if cursor < len(value):
            yield value[cursor:]

    def _build_fragment(self, spec: LogoSpec) -> ElementTree.Element:
        outer = ElementTree.Element(
            "span",
            {
                "class": f"tex-logo tex-{spec.slug}",
                "data-tex-command": spec.command,
                "data-tex-logo": spec.slug,
                "title": spec.description,
                "role": "img",
                "aria-label": spec.display,
                "style": _BASE_STYLE,
            },
        )

        builder = _HTML_BUILDERS.get(spec.slug, _build_plain_logo)
        builder(outer, spec)
        return outer

    def _is_code_element(self, element: ElementTree.Element) -> bool:
        tag = element.tag
        if isinstance(tag, str):
            tag = tag.lower()
        return tag in {"code", "pre"}

    def _is_logo_container(self, element: ElementTree.Element) -> bool:
        classes = element.get("class", "")
        if not isinstance(classes, str):
            return False
        return "tex-logo" in classes.split()


_BASE_STYLE = "font-family: 'Times New Roman', serif;"


def _build_plain_logo(container: ElementTree.Element, spec: LogoSpec) -> None:
    container.text = spec.display


def _build_tex_logo(container: ElementTree.Element, _: LogoSpec, *, prefix: str = "") -> None:
    container.text = f"{prefix}T"
    lowered_e = ElementTree.SubElement(
        container,
        "span",
        {"style": "position: relative; top: 0.2em; font-size: 0.8em;"},
    )
    lowered_e.text = "E"
    lowered_e.tail = "X"


def _build_latex_logo(
    container: ElementTree.Element, _: LogoSpec, *, prefix: str = ""
) -> ElementTree.Element:
    container.text = f"{prefix}L"
    raised_a = ElementTree.SubElement(
        container,
        "span",
        {"style": "position: relative; top: -0.3em; font-size: 0.8em;"},
    )
    raised_a.text = "A"
    raised_a.tail = "T"

    lowered_e = ElementTree.SubElement(
        container,
        "span",
        {"style": "position: relative; top: 0.2em; font-size: 0.8em;"},
    )
    lowered_e.text = "E"
    lowered_e.tail = "X"
    return lowered_e


def _build_latex(container: ElementTree.Element, spec: LogoSpec) -> None:
    _build_latex_logo(container, spec)


def _build_latex2e(container: ElementTree.Element, spec: LogoSpec) -> None:
    lowered_e = _build_latex_logo(container, spec)

    superscript_two = ElementTree.SubElement(
        container,
        "span",
        {"style": "position: relative; top: -0.35em; font-size: 0.65em; margin-left: 0.05em;"},
    )
    superscript_two.text = "2"

    epsilon = ElementTree.SubElement(
        container,
        "span",
        {
            "style": "position: relative; top: -0.2em; font-size: 0.7em; font-style: italic; margin-left: 0.02em;"
        },
    )
    epsilon.text = "\u03b5"
    lowered_e.tail = "X"


_HTML_BUILDERS: Mapping[str, Callable[[ElementTree.Element, LogoSpec], None]] = {
    "tex": _build_tex_logo,
    "latex": _build_latex,
    "latex2e": _build_latex2e,
}


class TexLogosExtension(Extension):
    """Register the TeX logo tree-processor."""

    def extendMarkdown(self, md: Markdown) -> None:  # type: ignore[override]  # noqa: N802
        md.treeprocessors.register(_TexLogosTreeprocessor(md), "texsmith_texlogos", priority=14)


def makeExtension(**_: object) -> TexLogosExtension:  # pragma: no cover - API hook  # noqa: N802
    return TexLogosExtension()


def _compile_pattern(mapping: Mapping[str, LogoSpec]) -> re.Pattern[str]:
    aliases = sorted(mapping.keys(), key=len, reverse=True)
    pattern = "|".join(re.escape(alias) for alias in aliases)
    return re.compile(pattern)


__all__ = ["TexLogosExtension", "makeExtension"]
