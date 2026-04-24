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
convention to plain Markdown tables: any paragraph of that shape is converted
into a ``<caption>`` child of the following ``<table>`` (plus an optional
``id`` from the ``{#label}`` part). Both the yaml-table renderer and the
legacy table renderer already consume ``<caption>`` directly, so no figure
wrapper is needed.

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

from .constants import Priority
from .html import build_error_element, render_error_html, render_table_html
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

_TABLE_CONFIG_ERROR_TITLE = "YAML table-config error"
_YAML_TABLE_ERROR_TITLE = "YAML table error"
_VALUE_ERROR_PREFIX = "Value error, "


@dataclass(slots=True)
class _CaptionInfo:
    text: str | None
    label: str | None


@dataclass(slots=True)
class _FenceBody:
    """Result of successfully scanning a fenced block.

    ``body`` is the de-indented payload between the opening and closing fence.
    ``indent`` is the leading whitespace common to both fences.
    ``end_index`` is the index (in the enclosing line list) of the first line
    *after* the closing fence.
    """

    body: str
    indent: str
    end_index: int


def _consume_fence(
    lines: list[str],
    start_index: int,
    fence_re: re.Pattern[str],
) -> _FenceBody | None:
    """Match ``lines[start_index]`` against ``fence_re`` and scan for its close.

    Returns ``None`` when the line doesn't open a fence or when no matching
    closing fence exists in the remainder of the list. On success returns the
    extracted body together with the indentation and the position after the
    closing fence, so the caller can replace the whole span atomically.
    """
    match = fence_re.match(lines[start_index])
    if match is None:
        return None

    fence = match.group("fence")
    indent = match.group("indent")
    close_re = re.compile(rf"^{re.escape(indent)}{re.escape(fence)}\s*$")

    body_lines: list[str] = []
    cursor = start_index + 1
    total = len(lines)
    while cursor < total:
        if close_re.match(lines[cursor]):
            if indent:
                body = "\n".join(
                    line[len(indent) :] if line.startswith(indent) else line for line in body_lines
                )
            else:
                body = "\n".join(body_lines)
            return _FenceBody(body=body, indent=indent, end_index=cursor + 1)
        body_lines.append(lines[cursor])
        cursor += 1
    return None


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


def _describe_parse_failure(exc: Exception) -> str:
    """Return a user-facing message for a YAML load / pydantic validation error."""
    if isinstance(exc, ValidationError):
        return _format_validation_error(exc)
    return str(exc)


def _load_yaml_table(body: str) -> Table:
    """Parse a YAML table body and return the validated :class:`Table`."""
    payload = yaml.safe_load(body)
    if payload is None:
        raise ValueError("empty yaml table payload")
    return parse_table(payload)


def _parse_table_config_body(body: str) -> TableConfig | str:
    """Return a validated :class:`TableConfig` or a human-readable error."""
    try:
        return parse_table_config(yaml.safe_load(body))
    except Exception as exc:
        return _describe_parse_failure(exc)


def _parse_caption_line(line: str) -> _CaptionInfo | None:
    match = _CAPTION_LINE_RE.match(line.strip())
    if match is None:
        return None
    caption = match.group("caption").strip() or None
    attrs = match.group("attrs") or ""
    label_match = _ID_ATTR_RE.search(attrs)
    label = label_match.group(1) if label_match else None
    return _CaptionInfo(text=caption, label=label)


# Each entry in the store is either a successfully parsed :class:`TableConfig`
# or a human-readable error message that should be surfaced as an admonition
# at block-processing time.
_ConfigEntry = TableConfig | str


def _ensure_config_store(md: Markdown) -> dict[int, _ConfigEntry]:
    store = getattr(md, "texsmith_table_configs", None)
    if store is None:
        store = {}
        md.texsmith_table_configs = store
    return store


# ---------------------------------------------------------------------------
# Preprocessor 1: ``yaml table`` fences → pre-rendered HTML placeholders
# ---------------------------------------------------------------------------


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
            extracted = _consume_fence(lines, index, _FENCE_OPEN_RE)
            if extracted is None:
                result.append(lines[index])
                index += 1
                continue

            caption_info = self._peek_caption(result)
            if caption_info is not None:
                # Drop the Table: line that we captured (plus any trailing blank).
                while result and not result[-1].strip():
                    result.pop()
                result.pop()  # the Table: line itself

            result.append(self._render_fence(extracted.body, caption=caption_info))
            index = extracted.end_index

        return result

    def _peek_caption(self, emitted: list[str]) -> _CaptionInfo | None:
        idx = len(emitted) - 1
        while idx >= 0 and not emitted[idx].strip():
            idx -= 1
        if idx < 0:
            return None
        return _parse_caption_line(emitted[idx])

    def _render_fence(self, body: str, *, caption: _CaptionInfo | None) -> str:
        try:
            table = _load_yaml_table(body)
        except Exception as exc:
            message = _describe_parse_failure(exc)
            return self.md.htmlStash.store(
                render_error_html(message, title=_YAML_TABLE_ERROR_TITLE)
            )

        html = render_table_html(
            table,
            caption=caption.text if caption else None,
            label=caption.label if caption else None,
        )
        return self.md.htmlStash.store(html)


# ---------------------------------------------------------------------------
# Preprocessor 2: ``yaml table-config`` fences → marker lines
# ---------------------------------------------------------------------------


class _TableConfigPreprocessor(Preprocessor):
    """Consume ``yaml table-config`` fences before any other fence handler runs.

    ``pymdownx.superfences`` registers a preprocessor at priority ``31.05``
    that scans for fence pairs early in the pipeline. When it encounters
    ``yaml table-config`` it finds ``table-config`` in its *unrecognised*
    group, abandons the opening fence — but leaves the closing fence in
    place. The next bare ``` ``` `` is then misread as a *new* opening fence,
    swallowing every intermediate line until the next fence. To avoid that we
    sit above superfences (see :class:`Priority`) and rewrite each fence span
    to a single marker line. The companion block processor turns the marker
    into a ``<texsmith-table-config>`` element that the treeprocessor binds
    to the preceding table.
    """

    def run(self, lines: list[str]) -> list[str]:  # type: ignore[override]
        result: list[str] = []
        index = 0
        total = len(lines)

        while index < total:
            extracted = _consume_fence(lines, index, _TABLE_CONFIG_FENCE_RE)
            if extracted is None:
                result.append(lines[index])
                index += 1
                continue

            # The outcome — success or error string — is persisted in the
            # shared store. A single marker line is emitted in both cases so
            # the block processor can decide how to render it. Using a marker
            # rather than ``htmlStash`` avoids NormalizeWhitespace (priority
            # 30) stripping the placeholder's control characters, since this
            # preprocessor has to sit above superfences at priority 32.
            store = _ensure_config_store(self.md)
            config_id = len(store)
            store[config_id] = _parse_table_config_body(extracted.body)
            result.append(extracted.indent + _TABLE_CONFIG_MARKER_FMT.format(id=config_id))
            index = extracted.end_index

        return result


# ---------------------------------------------------------------------------
# Block processor: raw ``yaml table-config`` fences (fallback) + markers
# ---------------------------------------------------------------------------


class _TableConfigBlockProcessor(BlockProcessor):
    """Emit a ``<texsmith-table-config>`` marker for each table-config block.

    Two entry points are recognised:

    1. The marker line ``texsmith-table-config-marker-N`` left by
       :class:`_TableConfigPreprocessor` (the normal path when superfences
       or any fence-eating preprocessor is installed).
    2. The raw ``yaml table-config`` fence, for pipelines that don't run the
       preprocessor (minimal tests, callers constructing a Markdown instance
       with only this extension).

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

        return self._consume_raw_fence(parent, blocks)

    def _consume_marker(
        self,
        parent: ElementTree.Element,
        blocks: list[str],
        marker_match: re.Match[str],
    ) -> bool:
        block = blocks.pop(0)
        config_id = int(marker_match.group("id"))
        store = _ensure_config_store(self.parser.md)
        entry = store.get(config_id)
        if isinstance(entry, str):
            parent.append(build_error_element(entry, title=_TABLE_CONFIG_ERROR_TITLE))
        elif entry is not None:
            marker = ElementTree.SubElement(
                parent,
                "texsmith-table-config",
                {"data-config-id": str(config_id)},
            )
            marker.text = ""
        # Stale ids (or lines the store no longer remembers) drop silently;
        # the treeprocessor would orphan them anyway.
        self._reinject_remainder(blocks, block, marker_match.end())
        return True

    @staticmethod
    def _reinject_remainder(blocks: list[str], block: str, marker_end: int) -> None:
        first_newline = block.find("\n", marker_end)
        if first_newline == -1:
            return
        remainder = block[first_newline + 1 :]
        if remainder.strip():
            blocks.insert(0, remainder)

    def _consume_raw_fence(
        self,
        parent: ElementTree.Element,
        blocks: list[str],
    ) -> bool:
        # Block processors receive pre-split blocks; a fenced span may cover
        # several of them when blank lines appear inside the payload. We
        # stitch consecutive blocks into a flat line list, scan once with the
        # shared fence helper, and then pop the blocks we consumed.
        stitched_lines: list[str] = []
        block_line_counts: list[int] = []
        for block in blocks:
            block_lines = block.split("\n")
            stitched_lines.extend(block_lines)
            block_line_counts.append(len(block_lines))

        extracted = _consume_fence(stitched_lines, 0, self._open_re)
        if extracted is None:
            return False

        consumed_lines = extracted.end_index
        blocks_to_drop = 0
        cumulative = 0
        for count in block_line_counts:
            blocks_to_drop += 1
            cumulative += count
            if cumulative >= consumed_lines:
                break
        for _ in range(blocks_to_drop):
            blocks.pop(0)

        outcome = _parse_table_config_body(extracted.body)
        if isinstance(outcome, str):
            parent.append(build_error_element(outcome, title=_TABLE_CONFIG_ERROR_TITLE))
            return True

        store = _ensure_config_store(self.parser.md)
        config_id = len(store)
        store[config_id] = outcome
        marker = ElementTree.SubElement(
            parent,
            "texsmith-table-config",
            {"data-config-id": str(config_id)},
        )
        marker.text = ""
        return True


# ---------------------------------------------------------------------------
# Treeprocessor 1: ``Table: caption {#label}`` paragraphs → <caption>
# ---------------------------------------------------------------------------


class _MarkdownTableCaptionTreeprocessor(Treeprocessor):
    """Attach ``Table: caption {#label}`` paragraphs to the following table.

    The paragraph is removed and its caption is inserted as a ``<caption>``
    child at the top of the next sibling ``<table>``; the ``{#label}`` part,
    if any, becomes the table's ``id``. Both the yaml-table renderer and the
    legacy table renderer consume ``<caption>`` directly, so no wrapper is
    needed.
    """

    def run(self, root: ElementTree.Element) -> ElementTree.Element | None:  # type: ignore[override]
        parent_map = _build_parent_map(root)

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

            self._attach_caption(parent, paragraph, table, info)

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
            # Any other element between caption and table means the user
            # didn't actually pair them up — leave everything alone.
            return None
        return None

    @staticmethod
    def _attach_caption(
        parent: ElementTree.Element,
        paragraph: ElementTree.Element,
        table: ElementTree.Element,
        info: _CaptionInfo,
    ) -> None:
        if table.find("caption") is None:
            caption = ElementTree.Element("caption")
            caption.text = info.text or ""
            table.insert(0, caption)
        if info.label and not table.get("id"):
            table.set("id", info.label)

        # Preserve the paragraph's trailing text on whichever neighbour will
        # still be there after removal — otherwise text between the caption
        # and the table is silently lost.
        children = list(parent)
        paragraph_index = children.index(paragraph)
        if paragraph.tail:
            if paragraph_index == 0:
                parent.text = (parent.text or "") + paragraph.tail
            else:
                previous = children[paragraph_index - 1]
                previous.tail = (previous.tail or "") + paragraph.tail
        parent.remove(paragraph)


# ---------------------------------------------------------------------------
# Treeprocessor 2: bind <texsmith-table-config> markers to preceding tables
# ---------------------------------------------------------------------------


class _TableConfigTreeprocessor(Treeprocessor):
    """Bind ``yaml table-config`` payloads to their preceding ``<table>``.

    The block processor stores parsed configs on ``md.texsmith_table_configs``
    and emits a ``<texsmith-table-config>`` marker. This processor walks the
    tree, locates each marker, finds the immediately preceding ``<table>``
    sibling, and writes layout decisions onto the table as ``data-ts-*``
    attributes so the yaml-table renderer takes over from there.
    """

    def run(self, root: ElementTree.Element) -> ElementTree.Element | None:  # type: ignore[override]
        store: dict[int, TableConfig] = getattr(self.md, "texsmith_table_configs", {})
        if not store:
            return None

        parent_map = _build_parent_map(root)

        for marker in list(root.iter("texsmith-table-config")):
            config_id = marker.get("data-config-id")
            table: ElementTree.Element | None = None
            if config_id is not None:
                try:
                    config = store[int(config_id)]
                except (KeyError, ValueError):
                    config = None
                else:
                    table = self._previous_table(parent_map, marker)
                if config is not None and table is not None:
                    _apply_config(table, config)
            _remove_marker(parent_map, marker)

        return None

    @staticmethod
    def _previous_table(
        parent_map: dict[ElementTree.Element, ElementTree.Element],
        marker: ElementTree.Element,
    ) -> ElementTree.Element | None:
        """Locate the closest preceding ``<table>`` at the marker's level.

        Markdown's block parser often wraps the htmlStash placeholder of a
        preceding element (or the marker itself) in a ``<p>``; we walk up the
        parent chain until we find a level whose previous sibling is a table.
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
                # Any other element breaks the pairing — the user didn't put
                # the config block immediately after the table.
                return None
            node = parent


def _apply_config(table: ElementTree.Element, config: TableConfig) -> None:
    from .constants import TableAttr

    n_columns = _count_table_columns(table)
    if n_columns < 2:
        return
    synthetic = synthesise_table_for_config(config, n_columns)
    layout = compute_layout(synthetic)
    table.set(TableAttr.TABLE, "1")
    table.set(TableAttr.ENV, layout.env)
    table.set(TableAttr.COLSPEC, layout.colspec)
    if layout.total_width_spec is not None:
        table.set(TableAttr.WIDTH, layout.total_width_spec)
    if layout.placement:
        table.set(TableAttr.PLACEMENT, layout.placement)


def _count_table_columns(table: ElementTree.Element) -> int:
    """Return the number of leaf columns in a Markdown-generated table."""
    for section_name in ("thead", "tbody"):
        section = table.find(section_name)
        if section is None:
            continue
        first_tr = section.find("tr")
        if first_tr is None:
            continue
        return sum(1 for _ in first_tr.findall("th")) + sum(1 for _ in first_tr.findall("td"))
    return 0


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _build_parent_map(
    root: ElementTree.Element,
) -> dict[ElementTree.Element, ElementTree.Element]:
    """Return a mapping from every descendant element to its parent."""
    parent_map: dict[ElementTree.Element, ElementTree.Element] = {}
    for parent in root.iter():
        for child in list(parent):
            parent_map[child] = parent
    return parent_map


def _remove_marker(
    parent_map: dict[ElementTree.Element, ElementTree.Element],
    marker: ElementTree.Element,
) -> None:
    parent = parent_map.get(marker)
    if parent is None:
        return
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


# ---------------------------------------------------------------------------
# Extension wiring
# ---------------------------------------------------------------------------


class YamlTableExtension(Extension):
    """Register the yaml-table handlers on the Markdown pipeline."""

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802
        md.preprocessors.register(
            _YamlTablePreprocessor(md), "texsmith_yaml_table", Priority.YAML_TABLE_PRE
        )
        md.preprocessors.register(
            _TableConfigPreprocessor(md),
            "texsmith_table_config",
            Priority.TABLE_CONFIG_PRE,
        )
        md.parser.blockprocessors.register(
            _TableConfigBlockProcessor(md.parser),
            "texsmith_table_config_fence",
            priority=Priority.TABLE_CONFIG_BLOCK,
        )
        md.treeprocessors.register(
            _MarkdownTableCaptionTreeprocessor(md),
            "texsmith_table_caption",
            Priority.CAPTION_TREE,
        )
        md.treeprocessors.register(
            _TableConfigTreeprocessor(md),
            "texsmith_table_config",
            Priority.CONFIG_TREE,
        )


def makeExtension(  # noqa: N802 - Markdown entry point contract
    **kwargs: object,
) -> YamlTableExtension:  # pragma: no cover - trivial factory
    return YamlTableExtension(**kwargs)


__all__ = ["YamlTableExtension", "makeExtension"]
