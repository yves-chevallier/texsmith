"""Markdown extension that turns ``yaml table`` fenced blocks into HTML.

The preprocessor captures fence blocks of the form::

    ```yaml table
    columns: [...]
    rows: [...]
    ```

It also absorbs an optional ``Table: <caption> {#label}`` line placed on the
line directly above the fence (the standard TeXSmith caption syntax) so the
generated ``<table>`` carries both ``<caption>`` and ``id`` attributes.

A companion treeprocessor applies the same ``Table: <caption> {#label}``
convention to plain Markdown tables: any paragraph of that shape is
reattached to the following ``<table>`` as a ``<figcaption>``, which the
existing ``render_figures`` handler migrates into a proper ``<caption>``.

Validation errors and YAML parsing errors surface as a visible admonition-shaped
error block so the document build fails loudly instead of silently dropping
the table.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from xml.etree import ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.treeprocessors import Treeprocessor
from pydantic import ValidationError
import yaml

from .html import render_error_html, render_table_html
from .schema import Table, parse_table


_FENCE_OPEN_RE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})yaml\s+table\s*$")
_CAPTION_LINE_RE = re.compile(r"^Table:\s*(?P<caption>.*?)(?:\s+\{(?P<attrs>[^}]+)\})?\s*$")
_ID_ATTR_RE = re.compile(r"#([A-Za-z][\w:.\-]*)")


@dataclass(slots=True)
class _CaptionInfo:
    text: str | None
    label: str | None


def _load_yaml_table(body: str) -> Table:
    """Parse a YAML table body and return the validated :class:`Table`."""
    payload = yaml.safe_load(body)
    if payload is None:
        raise ValueError("empty yaml table payload")
    return parse_table(payload)


_VALUE_ERROR_PREFIX = "Value error, "


def _format_validation_error(exc: ValidationError) -> str:
    """Strip the verbose pydantic framing from a validation error.

    Pydantic wraps our ``ValueError`` messages with location + type metadata;
    we only want the underlying human-readable message on its own line so the
    error admonition stays readable.
    """
    messages: list[str] = []
    for err in exc.errors():
        msg = str(err.get("msg", "")).strip()
        if msg.startswith(_VALUE_ERROR_PREFIX):
            msg = msg[len(_VALUE_ERROR_PREFIX) :]
        if msg:
            messages.append(msg)
    if not messages:
        return str(exc)
    return "\n".join(messages)


def _parse_caption_line(line: str) -> _CaptionInfo | None:
    match = _CAPTION_LINE_RE.match(line.strip())
    if match is None:
        return None
    caption = match.group("caption").strip() or None
    attrs = match.group("attrs") or ""
    label_match = _ID_ATTR_RE.search(attrs)
    label = label_match.group(1) if label_match else None
    return _CaptionInfo(text=caption, label=label)


class _YamlTablePreprocessor(Preprocessor):
    """Replace ``yaml table`` fences with pre-rendered HTML placeholders."""

    def run(self, lines: list[str]) -> list[str]:  # type: ignore[override]
        result: list[str] = []
        index = 0
        total = len(lines)

        while index < total:
            line = lines[index]
            match = _FENCE_OPEN_RE.match(line)
            if match is None:
                result.append(line)
                index += 1
                continue

            fence = match.group("fence")
            indent = match.group("indent")
            close_re = re.compile(rf"^{re.escape(indent)}{re.escape(fence)}\s*$")

            body_lines: list[str] = []
            fence_closed = False
            cursor = index + 1
            while cursor < total:
                if close_re.match(lines[cursor]):
                    fence_closed = True
                    break
                body_lines.append(lines[cursor])
                cursor += 1

            if not fence_closed:
                # No closing fence — leave the block untouched; Markdown will
                # surface its own error via the standard fenced-code parsing.
                result.append(line)
                index += 1
                continue

            caption_info = self._peek_caption(result)
            html_placeholder = self._render_fence(body_lines, indent=indent, caption=caption_info)
            if caption_info is not None:
                # Drop the Table: line that we captured (plus any trailing blank).
                while result and not result[-1].strip():
                    result.pop()
                result.pop()  # the Table: line itself

            result.append(html_placeholder)
            index = cursor + 1

        return result

    def _peek_caption(self, emitted: list[str]) -> _CaptionInfo | None:
        # Walk back past blank lines, then attempt to parse the first
        # non-blank preceding line as a Table: caption.
        idx = len(emitted) - 1
        while idx >= 0 and not emitted[idx].strip():
            idx -= 1
        if idx < 0:
            return None
        info = _parse_caption_line(emitted[idx])
        if info is None:
            return None
        return info

    def _render_fence(
        self,
        body_lines: list[str],
        *,
        indent: str,
        caption: _CaptionInfo | None,
    ) -> str:
        # Strip the common leading indentation so that YAML parses cleanly.
        if indent:
            body = "\n".join(
                line[len(indent) :] if line.startswith(indent) else line for line in body_lines
            )
        else:
            body = "\n".join(body_lines)

        try:
            table = _load_yaml_table(body)
        except ValidationError as exc:
            html = render_error_html(_format_validation_error(exc))
            return self._stash(html)
        except Exception as exc:
            html = render_error_html(str(exc))
            return self._stash(html)

        html = render_table_html(
            table,
            caption=caption.text if caption else None,
            label=caption.label if caption else None,
        )
        return self._stash(html)

    def _stash(self, html: str) -> str:
        return self.md.htmlStash.store(html)


class _MarkdownTableCaptionTreeprocessor(Treeprocessor):
    """Attach ``Table: caption {#label}`` paragraphs to the following table.

    Runs on the parsed tree so plain Markdown tables pick up the same caption
    syntax used by yaml-tables. The paragraph is rewritten into a ``<figure>``
    wrapping the table + ``<figcaption>``, which the existing
    ``render_figures`` handler migrates into a ``<caption>`` inside the table.
    """

    def run(self, root: ElementTree.Element) -> ElementTree.Element | None:  # type: ignore[override]
        parent_map: dict[ElementTree.Element, ElementTree.Element] = {}
        for parent in root.iter():
            for child in list(parent):
                parent_map[child] = parent

        for paragraph in list(root.iter("p")):
            info = self._caption_from_paragraph(paragraph)
            if info is None:
                continue

            parent = parent_map.get(paragraph)
            if parent is None:
                continue

            table = self._next_table_sibling(parent, paragraph)
            if table is None:
                continue

            self._wrap_table_with_caption(parent, paragraph, table, info)

        return None

    @staticmethod
    def _caption_from_paragraph(
        paragraph: ElementTree.Element,
    ) -> _CaptionInfo | None:
        if len(paragraph):
            # Caption paragraphs are expected to be plain text.
            return None
        text = (paragraph.text or "").strip()
        if not text.startswith("Table:"):
            return None
        return _parse_caption_line(text)

    @staticmethod
    def _next_table_sibling(
        parent: ElementTree.Element,
        paragraph: ElementTree.Element,
    ) -> ElementTree.Element | None:
        children = list(parent)
        try:
            index = children.index(paragraph)
        except ValueError:
            return None
        for candidate in children[index + 1 :]:
            if candidate.tag == "table":
                return candidate
            # Anything else between the caption paragraph and the table means
            # the user didn't actually pair them up — leave everything alone.
            return None
        return None

    @staticmethod
    def _wrap_table_with_caption(
        parent: ElementTree.Element,
        paragraph: ElementTree.Element,
        table: ElementTree.Element,
        info: _CaptionInfo,
    ) -> None:
        figure = ElementTree.Element("figure", {"class": "ts-table-figure"})
        if info.label:
            figure.set("id", info.label)
        figcaption = ElementTree.SubElement(figure, "figcaption")
        figcaption.text = info.text or ""

        children = list(parent)
        table_index = children.index(table)
        parent.remove(table)
        figure.append(table)
        # Transfer any trailing text from the original paragraph onto the
        # figure so the document flow is preserved.
        figure.tail = paragraph.tail
        # Replace paragraph at its own position with the figure.
        paragraph_index = children.index(paragraph)
        parent.remove(paragraph)
        # ``table_index`` may have shifted after the remove; recompute.
        insert_at = min(paragraph_index, len(list(parent)))
        parent.insert(insert_at, figure)
        _ = table_index  # kept for clarity; not needed after removals


class YamlTableExtension(Extension):
    """Register the ``yaml table`` preprocessor on the Markdown pipeline."""

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802
        md.preprocessors.register(_YamlTablePreprocessor(md), "texsmith_yaml_table", 29)
        md.treeprocessors.register(
            _MarkdownTableCaptionTreeprocessor(md), "texsmith_table_caption", 5
        )


def makeExtension(  # noqa: N802 - Markdown entry point contract
    **kwargs: object,
) -> YamlTableExtension:  # pragma: no cover - trivial factory
    return YamlTableExtension(**kwargs)


__all__ = ["YamlTableExtension", "makeExtension"]
