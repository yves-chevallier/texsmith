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
from markdown.blockprocessors import BlockParser, BlockProcessor
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.treeprocessors import Treeprocessor
from pydantic import ValidationError
import yaml

from .html import render_error_html, render_table_html
from .layout import compute_layout
from .schema import (
    Table,
    TableConfig,
    parse_table,
    parse_table_config,
    synthesise_table_for_config,
)


_FENCE_OPEN_RE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})yaml\s+table\s*$")
_TABLE_CONFIG_FENCE_RE = re.compile(
    r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})yaml\s+table-config\s*$"
)
# Marker left in the source by :class:`_TableConfigPreprocessor` and recognised
# by :class:`_TableConfigBlockProcessor`. Avoids ``\x02``/``\x03`` (those are
# claimed by Python-Markdown's htmlStash and would be stripped mid-pipeline).
_TABLE_CONFIG_MARKER_FMT = "texsmith-table-config-marker-{id}"
_TABLE_CONFIG_MARKER_RE = re.compile(
    r"^(?P<indent>\s*)texsmith-table-config-marker-(?P<id>\d+)\s*$"
)
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
    """Replace ``yaml table`` fences with pre-rendered HTML placeholders.

    ``yaml table-config`` fences are NOT consumed here — they are handled by
    :class:`_TableConfigBlockProcessor` so they can produce real ElementTree
    elements visible to treeprocessors (htmlStash placeholders only resolve
    at postprocessor time, too late to bind config to a sibling table).
    """

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


def _ensure_config_store(md: Markdown) -> dict[int, TableConfig]:
    store = getattr(md, "texsmith_table_configs", None)
    if store is None:
        store = {}
        md.texsmith_table_configs = store
    return store


class _TableConfigPreprocessor(Preprocessor):
    """Consume ``yaml table-config`` fences before any other fence handler runs.

    Why this is a preprocessor rather than a block processor: ``pymdownx.superfences``
    registers a preprocessor that scans for fence pairs early in the pipeline.
    When it encounters `````yaml table-config`` it parses the info
    string, finds ``table-config`` in the *unrecognized* group, and abandons the
    opening fence — but it does not skip the matching closing fence. The next
    bare ``````` is then misread as the *opening* of a new fenced
    block, swallowing every line up to the next fence (typically the next
    ``yaml table-config``). The downstream :class:`_TableConfigBlockProcessor`
    runs after preprocessing and never sees the original fences.

    The preprocessor parses the YAML body into a :class:`TableConfig`, stores it
    on ``md.texsmith_table_configs`` keyed by an auto-incrementing id, and
    replaces the entire fence span with a single marker line of the form
    ``texsmith-table-config:N``. The companion block processor
    recognises that marker and emits the same ``<texsmith-table-config>``
    element it would have produced from the raw fence.
    """

    def run(self, lines: list[str]) -> list[str]:  # type: ignore[override]
        result: list[str] = []
        index = 0
        total = len(lines)

        while index < total:
            line = lines[index]
            match = _TABLE_CONFIG_FENCE_RE.match(line)
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
                # Leave the fence intact; the block processor (or a downstream
                # error path) will surface the missing-close diagnostic.
                result.append(line)
                index += 1
                continue

            if indent:
                body = "\n".join(
                    bl[len(indent):] if bl.startswith(indent) else bl
                    for bl in body_lines
                )
            else:
                body = "\n".join(body_lines)

            store = _ensure_config_store(self.md)
            try:
                config = parse_table_config(yaml.safe_load(body))
            except (ValidationError, Exception):  # noqa: BLE001
                # On parse failure, leave the original fence in place so the
                # block processor produces the existing admonition-shaped error.
                result.extend(lines[index:cursor + 1])
                index = cursor + 1
                continue

            config_id = len(store)
            store[config_id] = config
            result.append(indent + _TABLE_CONFIG_MARKER_FMT.format(id=config_id))
            index = cursor + 1

        return result


class _TableConfigBlockProcessor(BlockProcessor):
    """Emit a ``<texsmith-table-config>`` marker for each table-config block.

    Two entry points are recognised, in priority order:

    1. The marker line ``texsmith-table-config:N`` left by
       :class:`_TableConfigPreprocessor`. This is the normal path when the
       preprocessor pipeline includes fence-eating extensions like
       ``pymdownx.superfences`` (pre-resolved configs are looked up by id).
    2. The raw `````yaml table-config`` fence, kept for
       pipelines that don't run the preprocessor (minimal tests, callers that
       construct a Markdown instance with only this extension).

    Either way, a ``<texsmith-table-config>`` element is created directly in
    the parser tree so the companion treeprocessor can bind it to the
    preceding ``<table>``.
    """

    def __init__(self, parser: BlockParser) -> None:
        super().__init__(parser)
        self._open_re = _TABLE_CONFIG_FENCE_RE
        self._marker_re = _TABLE_CONFIG_MARKER_RE

    def test(self, parent: ElementTree.Element, block: str) -> bool:  # type: ignore[override]
        first_line = block.split("\n", 1)[0]
        return bool(self._marker_re.match(first_line) or self._open_re.match(first_line))

    def run(  # type: ignore[override]
        self, parent: ElementTree.Element, blocks: list[str]
    ) -> bool:
        block = blocks[0]
        first_line = block.split("\n", 1)[0]

        marker_match = self._marker_re.match(first_line)
        if marker_match is not None:
            return self._consume_marker(parent, blocks, marker_match)

        return self._consume_fence(parent, blocks)

    def _consume_marker(
        self,
        parent: ElementTree.Element,
        blocks: list[str],
        marker_match: re.Match[str],
    ) -> bool:
        block = blocks.pop(0)
        config_id = int(marker_match.group("id"))
        store = _ensure_config_store(self.parser.md)
        if config_id not in store:
            # Stale or unknown id; drop silently rather than emitting a marker
            # the treeprocessor would orphan anyway.
            self._reinject_remainder(blocks, block, marker_match.end())
            return True

        marker = ElementTree.SubElement(
            parent,
            "texsmith-table-config",
            {"data-config-id": str(config_id)},
        )
        marker.text = ""
        self._reinject_remainder(blocks, block, marker_match.end())
        return True

    @staticmethod
    def _reinject_remainder(blocks: list[str], block: str, marker_end: int) -> None:
        # The first line is the marker (already consumed); push any trailing
        # lines back so the parser processes them as their own block.
        first_newline = block.find("\n", marker_end)
        if first_newline == -1:
            return
        remainder = block[first_newline + 1:]
        if remainder.strip():
            blocks.insert(0, remainder)

    def _consume_fence(
        self,
        parent: ElementTree.Element,
        blocks: list[str],
    ) -> bool:
        block = blocks[0]
        match = self._open_re.match(block.split("\n", 1)[0])
        if match is None:
            return False

        fence = match.group("fence")
        indent = match.group("indent")
        close_re = re.compile(rf"^{re.escape(indent)}{re.escape(fence)}\s*$")

        # Collect lines from this block (and possibly subsequent blocks)
        # until we hit the closing fence.
        body_lines: list[str] = []
        first_block_lines = block.split("\n")[1:]
        consumed_blocks = 1
        body, found = self._consume_block_lines(first_block_lines, close_re)
        body_lines.extend(body)
        while not found and consumed_blocks < len(blocks):
            body, found = self._consume_block_lines(
                blocks[consumed_blocks].split("\n"), close_re
            )
            body_lines.extend(body)
            consumed_blocks += 1
        if not found:
            return False

        # Pop consumed blocks (the parser hands us a list it expects us to mutate).
        for _ in range(consumed_blocks):
            blocks.pop(0)

        body_text = "\n".join(body_lines)
        if indent:
            body_text = "\n".join(
                line[len(indent) :] if line.startswith(indent) else line
                for line in body_text.split("\n")
            )

        store = _ensure_config_store(self.parser.md)
        try:
            config = parse_table_config(yaml.safe_load(body_text))
        except ValidationError as exc:
            self._emit_error_block(parent, _format_validation_error(exc))
            return True
        except Exception as exc:  # noqa: BLE001
            self._emit_error_block(parent, str(exc))
            return True

        config_id = len(store)
        store[config_id] = config
        marker = ElementTree.SubElement(
            parent,
            "texsmith-table-config",
            {"data-config-id": str(config_id)},
        )
        # Empty marker; the treeprocessor binds it to the preceding table.
        marker.text = ""
        return True

    @staticmethod
    def _consume_block_lines(
        lines: list[str], close_re: re.Pattern[str]
    ) -> tuple[list[str], bool]:
        body: list[str] = []
        for line in lines:
            if close_re.match(line):
                return body, True
            body.append(line)
        return body, False

    def _emit_error_block(self, parent: ElementTree.Element, message: str) -> None:
        # Create an admonition-shaped element (matches the yaml-table error
        # rendering used by the preprocessor).
        div = ElementTree.SubElement(parent, "div", {"class": "admonition error ts-table-error"})
        title = ElementTree.SubElement(div, "p", {"class": "admonition-title"})
        title.text = "YAML table-config error"
        pre = ElementTree.SubElement(div, "pre")
        code = ElementTree.SubElement(pre, "code")
        code.text = message


class _TableConfigTreeprocessor(Treeprocessor):
    """Bind ``yaml table-config`` payloads to their preceding ``<table>``.

    The block processor stores parsed configs on ``md.texsmith_table_configs``
    and emits a ``<texsmith-table-config>`` marker. This processor walks the
    tree, locates each marker, finds the immediately preceding ``<table>``
    sibling (skipping the optional ``<figure>`` wrapper added by the caption
    processor), and writes layout decisions onto the table as ``data-ts-*``
    attributes so the yaml-table renderer takes over from there.
    """

    def run(self, root: ElementTree.Element) -> ElementTree.Element | None:  # type: ignore[override]
        store: dict[int, TableConfig] = getattr(self.md, "texsmith_table_configs", {})
        if not store:
            return None

        parent_map: dict[ElementTree.Element, ElementTree.Element] = {}
        for parent in root.iter():
            for child in list(parent):
                parent_map[child] = parent

        for marker in list(root.iter("texsmith-table-config")):
            config_id = marker.get("data-config-id")
            if config_id is None:
                continue
            try:
                config = store[int(config_id)]
            except (KeyError, ValueError):
                self._remove_marker(parent_map, marker)
                continue

            table = self._previous_table(parent_map, marker)
            if table is None:
                # No table to apply config to; drop the marker silently.
                self._remove_marker(parent_map, marker)
                continue

            self._apply_config(table, config)
            self._remove_marker(parent_map, marker)

        return None

    @staticmethod
    def _previous_table(
        parent_map: dict[ElementTree.Element, ElementTree.Element],
        marker: ElementTree.Element,
    ) -> ElementTree.Element | None:
        """Locate the closest preceding ``<table>`` (skipping inline wrappers).

        The htmlStash placeholder is often wrapped in a ``<p>`` by Markdown's
        block parser; we walk up the parent chain until we find a level whose
        previous sibling is a table or a figure containing one.
        """
        node = marker
        while True:
            parent = parent_map.get(node)
            if parent is None:
                return None
            children = list(parent)
            try:
                index = children.index(node)
            except ValueError:
                return None
            for candidate in reversed(children[:index]):
                if candidate.tag == "table":
                    return candidate
                if candidate.tag == "figure":
                    inner = candidate.find("table")
                    if inner is not None:
                        return inner
                return None  # an unrelated element broke the pairing
            # No earlier siblings at this level — climb one level up.
            node = parent

    @staticmethod
    def _apply_config(table: ElementTree.Element, config: TableConfig) -> None:
        n_columns = _count_table_columns(table)
        if n_columns < 2:
            return
        synthetic = synthesise_table_for_config(config, n_columns)
        layout = compute_layout(synthetic)
        table.set("data-ts-table", "1")
        table.set("data-ts-env", layout.env)
        table.set("data-ts-colspec", layout.colspec)
        if layout.total_width_spec is not None:
            table.set("data-ts-width", layout.total_width_spec)
        if layout.placement:
            table.set("data-ts-placement", layout.placement)

    @staticmethod
    def _remove_marker(
        parent_map: dict[ElementTree.Element, ElementTree.Element],
        marker: ElementTree.Element,
    ) -> None:
        parent = parent_map.get(marker)
        if parent is None:
            return
        # Preserve the marker's tail so following text isn't lost.
        children = list(parent)
        try:
            idx = children.index(marker)
        except ValueError:
            return
        if marker.tail:
            if idx == 0:
                parent.text = (parent.text or "") + marker.tail
            else:
                prev = children[idx - 1]
                prev.tail = (prev.tail or "") + marker.tail
        parent.remove(marker)


def _count_table_columns(table: ElementTree.Element) -> int:
    """Return the number of leaf columns in a Markdown-generated table."""
    thead = table.find("thead")
    if thead is not None:
        first_tr = thead.find("tr")
        if first_tr is not None:
            return sum(1 for _ in first_tr.findall("th")) + sum(1 for _ in first_tr.findall("td"))
    tbody = table.find("tbody")
    if tbody is not None:
        first_tr = tbody.find("tr")
        if first_tr is not None:
            return sum(1 for _ in first_tr.findall("th")) + sum(1 for _ in first_tr.findall("td"))
    return 0


class YamlTableExtension(Extension):
    """Register the ``yaml table`` preprocessor on the Markdown pipeline."""

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802
        md.preprocessors.register(_YamlTablePreprocessor(md), "texsmith_yaml_table", 29)
        # Must outrank pymdownx.superfences' ``fenced_raw_block`` (priority 31.05)
        # so the table-config fence is consumed before any other fence handler
        # has a chance to misparse it.
        md.preprocessors.register(
            _TableConfigPreprocessor(md), "texsmith_table_config", 32
        )
        md.parser.blockprocessors.register(
            _TableConfigBlockProcessor(md.parser),
            "texsmith_table_config_fence",
            # Higher than fenced-code processors so we capture before they do.
            priority=180,
        )
        md.treeprocessors.register(
            _MarkdownTableCaptionTreeprocessor(md), "texsmith_table_caption", 5
        )
        # Run after the caption treeprocessor so the table is already
        # wrapped in a <figure> when we look for it.
        md.treeprocessors.register(_TableConfigTreeprocessor(md), "texsmith_table_config", 4)


def makeExtension(  # noqa: N802 - Markdown entry point contract
    **kwargs: object,
) -> YamlTableExtension:  # pragma: no cover - trivial factory
    return YamlTableExtension(**kwargs)


__all__ = ["YamlTableExtension", "makeExtension"]
