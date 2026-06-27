"""``TypstWriter`` — emit Typst markup from the TeXSmith IR.

This is the project's *second* backend: it consumes the **same** IR the LaTeX
writer does (``readers/`` and ``ir/`` are untouched), proving the architecture
pays off. The writer is a typed visitor over :mod:`texsmith.ir`; each covered
node class has an emitter registered with the shared
:func:`~texsmith.writers.registry.writes` decorator and dispatch is keyed by
node class along the MRO.

Coverage now reaches **full IR-node parity with the LaTeX backend**: Document,
Para/Plain, Header, all inline emphasis (Emph/Strong/Strikeout/Underline/
Highlight/SmallCaps/Sub/Superscript/Quoted), Code/CodeBlock, Math, Link, Cite,
Note (footnote), IndexEntry, TexLogo, Keystroke, MarginNote, ProgressBar, Span
(footnote-ref/abbr/label + transparent), Bullet/OrderedList, DefinitionList,
BlockQuote, Admonition, Div, HorizontalRule, Image, Figure, and **both** simple
(GFM) and rich (yaml/data-ts) Tables — the latter rebuilt as a native Typst
``#table`` (column groups, multirow/multicolumn spans, labelled separators,
footer) from the validated tables-schema model. Any IR node without a Typst
emitter still raises :class:`TypstWriteError` — an explicit, localised error
naming the node type and the backend, mirroring the LaTeX backend's
``LaTeXWriteError``.

Math note: the IR carries *TeX* math source (``Math.text``), and the HtmlReader
encodes math typed inline in text as a *latex* ``RawInline`` (a documented IR
friction). Both are rendered through the Typst ``mitex`` package (a LaTeX-math
renderer); the scaffolding imports it on demand, so the source is reproduced
faithfully rather than dropped or mis-parsed by Typst's native math mode.

Citations: ``Cite`` and citation-shaped ``footnote-ref`` spans emit native
``#cite(<key>)`` markers resolved against the bibliography collection the CLI
builds (``.bib`` files + inline DOI), which the scaffolding wires via
``#bibliography(...)``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from texsmith.ir import nodes as ir
from texsmith.writers.registry import WriterRegistry, writes

from .._ir_queries import (
    _citation_keys_from_payload,
    _find_image,
    _find_table,
    _normalise_footnote_id,
    _split_citation_keys,
)
from .escaper import escape_typst_chars


if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence

    from .state import TypstWriterState


_LIST_INDENT = "  "


class TypstWriter:
    """Visitor that turns an IR document into a Typst markup string."""

    def __init__(self, state: TypstWriterState) -> None:
        self.state = state
        self._invalid_footnotes: set[str] = set()
        cls = type(self)
        # One registry per concrete class (a subclass that adds ``@writes``
        # emitters gets its own, not the base class's cached one).
        registry = cls.__dict__.get("_registry")
        if registry is None:
            registry = WriterRegistry()
            registry.collect_from_class(cls)
            cls._registry = registry  # type: ignore[attr-defined]
        self.registry = registry

    # -- public API --------------------------------------------------------

    def write(self, document: ir.Document) -> str:
        """Render a full document IR to a Typst body."""
        self._collect_footnotes(document)
        return self._join_blocks(document.content)

    # -- footnote pre-pass -------------------------------------------------

    def _collect_footnotes(self, document: ir.Document) -> None:
        """Harvest footnote-definition bodies, keyed by normalised id.

        Mirrors the LaTeX writer's pre-pass: a ``Div role=footnote-def
        id=<fn>`` is reduced to its single-line text so a ``footnote-ref`` site
        can resolve to a Typst ``#footnote`` or a ``@key`` citation.
        """
        from texsmith.ir.visitor import walk

        footnotes: dict[str, str] = {}
        for node in walk(document):
            if not isinstance(node, ir.Div):
                continue
            attrs = dict(node.attrs)
            if attrs.get("role") != "footnote-def":
                continue
            footnote_id = _normalise_footnote_id(attrs.get("id"))
            if not footnote_id:
                continue
            text = self.render_inline_blocks(node.content).strip()
            lines = [line for line in text.splitlines() if line.strip()]
            if len(lines) > 1:
                # Multi-line footnote bodies are dropped (same as LaTeX);
                # record so the reference site emits nothing rather than warning.
                self._invalid_footnotes.add(footnote_id)
                continue
            footnotes[footnote_id] = text.strip()
        if footnotes:
            self.state.footnotes.update(footnotes)

    # -- dispatch ----------------------------------------------------------

    def emit(self, node: ir.Node) -> str:
        """Emit a single node, dispatching by type."""
        method = self.registry.method_for(node)
        if method is None:
            raise TypstWriteError(node)
        return getattr(self, method)(node)

    def _join_blocks(self, blocks: Sequence[ir.Block]) -> str:
        parts = [self.emit(block) for block in blocks]
        return "\n\n".join(part for part in parts if part.strip())

    def _inlines(self, inlines: Sequence[ir.Inline]) -> str:
        return "".join(self.emit(node) for node in inlines)

    def render_blocks(self, blocks: Sequence[ir.Block]) -> str:
        """Render a sequence of blocks as full block-level Typst markup.

        Used by the templated emitter for named-slot bodies (e.g. a poster's
        quadrant), preserving paragraph/list structure — unlike
        :meth:`render_inline_blocks`, which flattens to a single line.
        """
        return self._join_blocks(blocks)

    def render_inline_blocks(self, blocks: Sequence[ir.Block]) -> str:
        """Render blocks as inline-ish content (footnote / definition / slot bodies).

        Public entry point used by the templated emitter to render slot content
        (e.g. an abstract) outside the document body.
        """
        parts: list[str] = []
        for block in blocks:
            if isinstance(block, (ir.Plain, ir.Para)):
                parts.append(self._inlines(block.content).strip())
            else:
                parts.append(self.emit(block))
        return " ".join(part for part in parts if part.strip())

    # ----------------------------------------------------------------- #
    # Inline emitters
    # ----------------------------------------------------------------- #

    @writes(ir.Str)
    def _str(self, node: ir.Str) -> str:
        return escape_typst_chars(node.text)

    @writes(ir.Space)
    def _space(self, _node: ir.Space) -> str:
        return " "

    @writes(ir.SoftBreak)
    def _softbreak(self, _node: ir.SoftBreak) -> str:
        return "\n"

    @writes(ir.LineBreak)
    def _linebreak(self, _node: ir.LineBreak) -> str:
        return " \\\n"

    @writes(ir.Emph)
    def _emph(self, node: ir.Emph) -> str:
        return f"_{self._inlines(node.content)}_"

    @writes(ir.Strong)
    def _strong(self, node: ir.Strong) -> str:
        return f"*{self._inlines(node.content)}*"

    @writes(ir.Strikeout)
    def _strikeout(self, node: ir.Strikeout) -> str:
        return f"#strike[{self._inlines(node.content)}]"

    @writes(ir.Underline)
    def _underline(self, node: ir.Underline) -> str:
        return f"#underline[{self._inlines(node.content)}]"

    @writes(ir.Highlight)
    def _highlight(self, node: ir.Highlight) -> str:
        return f"#highlight[{self._inlines(node.content)}]"

    @writes(ir.SmallCaps)
    def _smallcaps(self, node: ir.SmallCaps) -> str:
        return f"#smallcaps[{self._inlines(node.content)}]"

    @writes(ir.Subscript)
    def _subscript(self, node: ir.Subscript) -> str:
        return f"#sub[{self._inlines(node.content)}]"

    @writes(ir.Superscript)
    def _superscript(self, node: ir.Superscript) -> str:
        return f"#super[{self._inlines(node.content)}]"

    @writes(ir.Quoted)
    def _quoted(self, node: ir.Quoted) -> str:
        # Typst's smart-quote handling turns a straight double quote into the
        # locale-appropriate typographic pair around the enclosed content.
        return f'"{self._inlines(node.content)}"'

    @writes(ir.Cite)
    def _cite(self, node: ir.Cite) -> str:
        for key in node.keys:
            self.state.record_citation(key)
        return self._citation_markup(node.keys)

    @writes(ir.Note)
    def _note(self, node: ir.Note) -> str:
        body = self.render_inline_blocks(node.content).strip()
        return f"#footnote[{body}]"

    @writes(ir.IndexEntry)
    def _index(self, node: ir.IndexEntry) -> str:
        # Typst has no first-class index; surface any visible text and otherwise
        # contribute nothing (the entry is an out-of-band marker).
        return self._inlines(node.visible).strip()

    @writes(ir.TexLogo)
    def _texlogo(self, node: ir.TexLogo) -> str:
        return _TEXLOGO_TEXT.get(node.name, "LaTeX")

    @writes(ir.Keystroke)
    def _keystroke(self, node: ir.Keystroke) -> str:
        keys = [escape_typst_chars(key) for key in node.keys]
        return "+".join(
            f"#box(stroke: 0.5pt, inset: (x: 3pt), outset: (y: 2pt))[{k}]" for k in keys
        )

    @writes(ir.MarginNote)
    def _marginnote(self, node: ir.MarginNote) -> str:
        # Typst has no dependency-free margin-note primitive; degrade to a
        # ``#footnote`` (the closest native aside) so the supplementary content
        # is preserved rather than dropped — mirroring the graceful degradation
        # the Admonition emitter applies. The ``side`` hint has no counterpart.
        body = self.render_inline_blocks(node.content).strip()
        return f"#footnote[{body}]" if body else ""

    @writes(ir.Span)
    def _span(self, node: ir.Span) -> str:
        return self._render_span(node)

    @writes(ir.Code)
    def _code(self, node: ir.Code) -> str:
        # Inline raw text; pick a backtick fence longer than any run inside.
        return _raw_inline(node.text)

    @writes(ir.Math)
    def _math(self, node: ir.Math) -> str:
        # The IR carries *TeX* math source. Typst's native math syntax differs,
        # so we render it through the ``mitex`` package (a LaTeX-math renderer),
        # flagging the runtime so the scaffolding imports it.
        return self._mitex(node.text.strip(), display=node.display)

    def _mitex(self, tex: str, *, display: bool) -> str:
        """Render TeX math source via the ``mitex`` package.

        Equation cross-references get native-Typst handling because ``mitex``
        labels do not propagate to the document: a math span that is purely
        ``\\eqref{k}`` / ``\\ref{k}`` becomes a Typst ``#ref``, and an embedded
        ``\\label{k}`` is stripped from the source and re-attached as a Typst
        label on the emitted (now numbered) equation so the reference resolves.
        """
        ref_match = _PURE_EQREF_RE.match(tex)
        if ref_match:
            label = citation_label(ref_match.group(1))
            if label:
                self.state.runtime["uses_eqnref"] = True
                return f"#ref(<{label}>)"

        labels = _LABEL_RE.findall(tex)
        tex = _LABEL_RE.sub("", tex).strip()

        self.state.runtime["uses_mitex"] = True
        fence = _fence_for(tex)
        if display:
            call = f"#mitex({fence}{tex}{fence})"
            if labels:
                label = citation_label(labels[0])
                if label:
                    self.state.runtime["uses_eqnref"] = True
                    return f"{call} <{label}>"
            return call
        return f"#mi({fence}{tex}{fence})"

    @writes(ir.Link)
    def _link(self, node: ir.Link) -> str:
        target = node.target
        body = self._inlines(node.content)
        if not body:
            return f'#link("{_escape_string(target)}")'
        return f'#link("{_escape_string(target)}")[{body}]'

    @writes(ir.Image)
    def _image(self, node: ir.Image) -> str:
        call = self._image_call(node)
        return f"#{call}" if call else ""

    def _image_call(self, node: ir.Image) -> str:
        """Return a bare ``image(...)`` call, resolving the source via the map.

        Returns the expression *without* a leading ``#`` so it can be embedded in
        a code context (e.g. ``#figure(image(...), ...)``); the top-level image
        emitter prepends ``#``. ``state.runtime["image_map"]`` maps an original
        ``src`` to a path guaranteed to exist next to the ``.typ`` (or an empty
        string when the asset could not be made available, in which case the
        image is dropped so the document still compiles).
        """
        image_map = self.state.runtime.get("image_map")
        src = node.src
        if isinstance(image_map, dict):
            if node.src not in image_map:
                return ""  # unresolved remote/missing asset -> drop, keep compilable
            src = image_map[node.src]
            if not src:
                return ""
        if node.width:
            return f'image("{_escape_string(src)}", width: {node.width})'
        return f'image("{_escape_string(src)}")'

    @writes(ir.RawInline)
    def _raw_inline(self, node: ir.RawInline) -> str:
        # Per the IR contract a raw escape hatch is emitted only for its own
        # backend; ``typst`` payloads pass through verbatim.
        if node.format == "typst":
            return node.text
        # The HtmlReader encodes math typed inline in text (``$x$`` / ``\(x\)``)
        # as a *latex* raw inline (a documented IR friction). Recover the math
        # payload and render it through ``mitex`` rather than dropping it.
        if node.format == "latex":
            payload = _latex_inline_math_payload(node.text)
            if payload is not None:
                return self._mitex(payload, display=False)
        return ""

    # ----------------------------------------------------------------- #
    # Block emitters
    # ----------------------------------------------------------------- #

    @writes(ir.Para)
    def _para(self, node: ir.Para) -> str:
        # A paragraph whose sole content is an image renders as a centred figure
        # (mirrors the LaTeX backend, where a bare block image becomes a figure
        # captioned by its alt/title) rather than a left-aligned inline image.
        if len(node.content) == 1 and isinstance(node.content[0], ir.Image):
            return self._standalone_image(node.content[0])
        return self._inlines(node.content).strip()

    def _standalone_image(self, node: ir.Image) -> str:
        """Render a block-level image as a centred (optionally captioned) figure."""
        call = self._image_call(node)
        if not call:
            return ""
        caption = self._inlines(node.alt).strip() if node.alt else ""
        if not caption and node.title:
            caption = escape_typst_chars(node.title.strip())
        if caption:
            return f"#figure(\n  {call},\n  caption: [{caption}],\n)"
        return f"#align(center)[#{call}]"

    @writes(ir.Plain)
    def _plain(self, node: ir.Plain) -> str:
        return self._inlines(node.content).strip()

    @writes(ir.Header)
    def _header(self, node: ir.Header) -> str:
        level = max(1, node.level + self.state.heading_offset)
        marker = "=" * level
        text = self._inlines(node.content).strip()
        return f"{marker} {text}"

    @writes(ir.CodeBlock)
    def _code_block(self, node: ir.CodeBlock) -> str:
        lang = node.lang if node.lang and node.lang != "text" else ""
        body = node.text.rstrip("\n")
        fence = _fence_for(body)
        return f"{fence}{lang}\n{body}\n{fence}"

    @writes(ir.BlockQuote)
    def _blockquote(self, node: ir.BlockQuote) -> str:
        inner = self._join_blocks(node.content)
        indented = _indent(inner, "  ")
        return f"#quote(block: true)[\n{indented}\n]"

    @writes(ir.BulletList)
    def _bullet_list(self, node: ir.BulletList) -> str:
        return self._render_list(node.items, "-")

    @writes(ir.OrderedList)
    def _ordered_list(self, node: ir.OrderedList) -> str:
        return self._render_list(node.items, "+")

    def _render_list(self, items: Sequence[Sequence[ir.Block]], marker: str) -> str:
        lines: list[str] = []
        for item in items:
            body = self._list_item_body(item)
            first, *rest = body.split("\n")
            lines.append(f"{marker} {first}")
            for line in rest:
                lines.append(f"{_LIST_INDENT}{line}" if line else line)
        return "\n".join(lines)

    def _list_item_body(self, blocks: Sequence[ir.Block]) -> str:
        parts: list[str] = []
        for block in blocks:
            if isinstance(block, (ir.Plain, ir.Para)):
                parts.append(self._inlines(block.content).strip())
            else:
                parts.append(self.emit(block))
        return "\n".join(part for part in parts if part.strip())

    @writes(ir.HorizontalRule)
    def _hr(self, _node: ir.HorizontalRule) -> str:
        return "#line(length: 100%)"

    @writes(ir.ProgressBar)
    def _progressbar(self, node: ir.ProgressBar) -> str:
        # A native Typst bar: a fixed-width rounded track clipping a filled
        # box whose width is the fraction (relative to the track). No external
        # package needed — built from ``#box`` primitives.
        fraction = max(0.0, min(1.0, node.fraction))
        pct = f"{fraction * 100:g}%"
        height = "6pt" if node.thin else "12pt"
        label = self._inlines(node.label).strip() if node.label else pct
        track = (
            f"#box(width: 9cm, height: {height}, radius: 1pt, stroke: 0.5pt, "
            f"fill: luma(90%), clip: true)[#box(width: {pct}, height: 100%, "
            f"fill: luma(40%))[]]"
        )
        suffix = f" {label}" if label else ""
        return f"{track}{suffix}"

    @writes(ir.Figure)
    def _figure(self, node: ir.Figure) -> str:
        caption = self._inlines(node.caption).strip() if node.caption else ""
        image = _find_image(node.content)
        table = _find_table(node.content)
        if image is not None:
            body = self._image_call(image)
        elif table is not None:
            body = self._table_call(table)
        else:
            inner = self._join_blocks(node.content)
            body = f"[\n{_indent(inner, '  ')}\n]" if inner.strip() else ""
        if not body.strip():
            # The figure's only content was a dropped (unresolvable) image.
            return ""
        if caption:
            return f"#figure(\n  {_indent(body, '  ').lstrip()},\n  caption: [{caption}],\n)"
        return f"#figure(\n  {_indent(body, '  ').lstrip()},\n)"

    @writes(ir.Table)
    def _table(self, node: ir.Table) -> str:
        call = self._table_call(node)
        caption = self._inlines(node.caption).strip() if node.caption else ""
        if caption:
            return f"#figure(\n  {_indent(call, '  ').lstrip()},\n  caption: [{caption}],\n)"
        return f"#{call}"

    @writes(ir.RawBlock)
    def _raw_block(self, node: ir.RawBlock) -> str:
        return node.text if node.format == "typst" else ""

    @writes(ir.Document)
    def _document(self, node: ir.Document) -> str:
        return self._join_blocks(node.content)

    @writes(ir.Admonition)
    def _admonition(self, node: ir.Admonition) -> str:
        title = self._inlines(node.title).strip()
        body = self._join_blocks(node.content)
        cfg = self._callout_config(node.kind)
        style = (self.state.callout_style or "fancy").strip().lower()
        if style == "classic":
            return _callout_classic(title, body, cfg)
        if style == "minimal":
            return _callout_minimal(title, body, cfg)
        return _callout_fancy(title, body, cfg)

    def _callout_config(self, kind: str) -> dict[str, object]:
        """Return the callout definition for ``kind`` (falling back to default)."""
        callouts = self.state.callouts
        key = (kind or "").strip().lower()
        if key in callouts:
            return callouts[key]
        if "default" in callouts:
            return callouts["default"]
        return {"background_color": "f0f0f0", "border_color": "808080", "icon": "ℹ"}  # noqa: RUF001

    @writes(ir.DefinitionList)
    def _definition_list(self, node: ir.DefinitionList) -> str:
        lines: list[str] = []
        for item in node.items:
            term = self._inlines(item.term).strip()
            lines.append(f"/ {term}: ")
            for definition in item.definitions:
                body = self.render_inline_blocks(definition).strip()
                if lines[-1].endswith(": "):
                    lines[-1] = lines[-1] + body
                else:
                    lines.append(f"  {body}")
        return "\n".join(lines)

    @writes(ir.Div)
    def _div(self, node: ir.Div) -> str:
        role = dict(node.attrs).get("role", "")
        # Footnote containers are resolved at the reference site; emit nothing.
        if role in {"footnotes", "footnote-def"}:
            return ""
        return self._join_blocks(node.content)

    # -- span dispatch by role --------------------------------------------

    def _render_span(self, node: ir.Span) -> str:
        attrs = dict(node.attrs)
        role = attrs.get("role", "")
        if role == "abbr":
            return self._render_abbr(node, attrs.get("title", ""))
        if role == "footnote-ref":
            return self._render_footnote_ref(node, attrs.get("ref", ""))
        if role == "label":
            label = attrs.get("id", "").strip()
            return f"<{label}>" if label else ""
        # Plain / transparent span (emoji, critic, script, …): render children.
        return self._inlines(node.content)

    def _render_abbr(self, node: ir.Span, title: str) -> str:
        term = self._inlines(node.content).strip()
        description = title.strip()
        if term and description:
            # Record the first-seen description; render the short form.
            self.state.abbreviations.setdefault(term, description)
        return term

    def _render_footnote_ref(self, node: ir.Span, ref: str) -> str:
        footnote_id = _normalise_footnote_id(ref)
        if footnote_id in self._invalid_footnotes:
            return ""
        bibliography = self.state.bibliography
        payload = self.state.footnotes.get(footnote_id)

        # A footnote body that is purely a comma-separated citation key list (or
        # an id that is itself a bibliography key) resolves to a citation.
        keys = _citation_keys_from_payload(payload)
        if not keys:
            keys = _split_citation_keys(footnote_id)
        if keys and all(key in bibliography for key in keys):
            for key in keys:
                self.state.record_citation(key)
            return self._citation_markup(keys)
        if footnote_id in bibliography:
            self.state.record_citation(footnote_id)
            return self._citation_markup([footnote_id])
        if payload:
            return f"#footnote[{payload}]"
        # Unresolved reference: keep the rendered marker text.
        return self._inlines(node.content)

    def _citation_markup(self, keys: Sequence[str]) -> str:
        return "".join(f"#cite(<{citation_label(key)}>)" for key in keys)

    # -- table -------------------------------------------------------------

    def _table_call(self, node: ir.Table) -> str:
        """Return a bare ``table(...)`` call (no leading ``#``, no caption)."""
        from texsmith.extensions.tables import schema as tbl

        if node.env or node.colspec:
            # Rich (yaml/data-ts) tables carry pre-computed LaTeX layout; the
            # Typst backend rebuilds the equivalent native ``#table`` directly
            # from the validated model (groups, spans, separators, footer).
            return self._rich_table_call(node)

        model = node.model
        leaves: list[tbl.LeafColumn] = []
        for column in model.columns:
            leaves.extend(tbl.column_leaves(column))
        n_cols = len(leaves)
        if n_cols == 0:  # pragma: no cover - schema enforces >= 2 columns
            raise TypstWriteError(node, detail="table without columns")
        aligns = [_TYPST_ALIGN.get((leaf.align or "l"), "left") for leaf in leaves]

        cells = [self._inlines(cell).strip() for cell in node.cells]
        cursor = 0
        header = cells[cursor : cursor + n_cols]
        cursor += n_cols
        rows: list[list[str]] = []
        for row in model.rows:
            if isinstance(row, tbl.Separator):
                continue
            width = 1 + len(row.cells)
            rows.append(cells[cursor : cursor + width])
            cursor += width

        lines = [
            "table(",
            f"  columns: {n_cols},",
            f"  align: ({', '.join(aligns)}),",
            "  table.header(" + ", ".join(f"[{c}]" for c in header) + "),",
        ]
        for row in rows:
            lines.append("  " + ", ".join(f"[{c}]" for c in row) + ",")
        return "\n".join(lines) + "\n)"

    # -- rich (yaml / data-ts) table --------------------------------------

    def _rich_table_call(self, node: ir.Table) -> str:
        """Rebuild a rich table as a native Typst ``#table`` from the model.

        The IR carries the validated tables-schema ``model`` (the shape SSOT:
        column groups, multirow/multicolumn spans, separators, footer) plus the
        rendered inline ``cells`` (document order). We regenerate the canonical
        ``data-ts`` HTML for the shape, inject the writer-rendered Typst cell
        content into it (matching the LaTeX yaml path), then translate the
        ``thead``/``tbody``/``tfoot`` rows into Typst ``table.header(...)``,
        ``table.cell(colspan/rowspan/align)`` cells and ``table.hline()``
        separators. Typst auto-flows cells by column count and skips positions
        consumed by a span, so the HTML's "absorbed slots omitted" convention
        maps directly without manual cursor threading.
        """
        from bs4 import BeautifulSoup
        from bs4.element import Tag

        from texsmith.extensions.tables import schema as tbl
        from texsmith.extensions.tables.html import render_table_html

        model = node.model
        total_cols = tbl.total_leaves(model.columns)
        leaves: list[tbl.LeafColumn] = []
        for column in model.columns:
            leaves.extend(tbl.column_leaves(column))

        html = render_table_html(model)
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not isinstance(table, Tag):  # pragma: no cover - defensive
            raise TypstWriteError(node, detail="rich (yaml/data-ts) tables")

        # Inject the writer-rendered inline content (document order, caption and
        # separator-row cells excluded — same set as ``node.cells``).
        rendered = [self._inlines(cell).strip() for cell in node.cells]
        html_cells = [
            c
            for c in table.find_all(["th", "td"])
            if c.find_parent("caption") is None and not _in_separator_row(c)
        ]
        for cell, content in zip(html_cells, rendered, strict=False):
            cell.clear()
            cell.append(content)

        columns_spec = _rich_columns_spec(leaves, total_cols)
        aligns = ", ".join(_TYPST_ALIGN.get((leaf.align or "l"), "left") for leaf in leaves)

        lines = [
            "table(",
            f"  columns: {columns_spec},",
            f"  align: ({aligns}),",
        ]

        thead = table.find("thead")
        if isinstance(thead, Tag):
            header_cells: list[str] = []
            for tr in thead.find_all("tr", recursive=False):
                header_cells.extend(_rich_row_cells(tr))
            lines.append("  table.header(" + ", ".join(header_cells) + "),")

        for section_name in ("tbody", "tfoot"):
            section = table.find(section_name)
            if not isinstance(section, Tag):
                continue
            if section_name == "tfoot":
                # An extra rule splits summary rows from the body.
                lines.append("  table.hline(),")
            lines.extend(_rich_section_lines(section, total_cols))

        return "\n".join(lines) + "\n)"


_TYPST_ALIGN = {"l": "left", "c": "center", "r": "right", "j": "left"}


def _rich_section_lines(section: object, total_cols: int) -> list[str]:
    """Translate a ``<tbody>``/``<tfoot>`` into Typst row / hline lines."""
    from bs4.element import Tag

    from texsmith.adapters.html_utils import coerce_attribute
    from texsmith.extensions.tables.constants import TableAttr

    lines: list[str] = []
    if not isinstance(section, Tag):  # pragma: no cover - defensive
        return lines
    for tr in section.find_all("tr", recursive=False):
        if coerce_attribute(tr.get(TableAttr.ROLE)) == "separator":
            rule = coerce_attribute(tr.get(TableAttr.RULE))
            lines.append("  table.hline(stroke: 1pt)," if rule == "double" else "  table.hline(),")
            cell = tr.find(["td", "th"])
            label = cell.get_text(strip=False).strip() if cell is not None else ""
            if label:
                lines.append(f"  table.cell(colspan: {total_cols})[_{escape_typst_chars(label)}_],")
            continue
        lines.append("  " + ", ".join(_rich_row_cells(tr)) + ",")
    return lines


def _rich_row_cells(tr: object) -> list[str]:
    """Render every ``<th>``/``<td>`` in a row to a Typst cell expression."""
    from texsmith.adapters.html_utils import coerce_attribute
    from texsmith.extensions.tables.constants import TableAttr

    cells: list[str] = []
    for cell in tr.find_all(["th", "td"], recursive=False):  # type: ignore[attr-defined]
        rowspan = int(coerce_attribute(cell.get("rowspan")) or 1)
        colspan = int(coerce_attribute(cell.get("colspan")) or 1)
        align = coerce_attribute(cell.get(TableAttr.ALIGN))
        content = cell.get_text(strip=False).strip()
        cells.append(_rich_cell(content, rowspan, colspan, align))
    return cells


def _rich_columns_spec(leaves: Sequence[object], total_cols: int) -> str:
    """Return a Typst ``columns:`` value from the leaf column widths.

    ``X`` (tabularx fill) → ``1fr``; an ``NN%`` width passes through as a Typst
    relative length; everything else (natural / opaque LaTeX lengths) → ``auto``.
    When every column is auto we emit the bare integer count.
    """
    widths: list[str] = []
    any_sized = False
    for leaf in leaves:
        width = getattr(leaf, "width", None)
        if width == "X":
            widths.append("1fr")
            any_sized = True
        elif isinstance(width, str) and width.endswith("%"):
            widths.append(width)
            any_sized = True
        else:
            widths.append("auto")
    if not any_sized:
        return str(total_cols)
    return "(" + ", ".join(widths) + ")"


def _rich_cell(content: str, rowspan: int, colspan: int, align: object) -> str:
    """Render one rich-table cell as a Typst content cell or ``table.cell(...)``."""
    body = f"[{content}]"
    args: list[str] = []
    if colspan > 1:
        args.append(f"colspan: {colspan}")
    if rowspan > 1:
        args.append(f"rowspan: {rowspan}")
    if align in {"l", "c", "r", "j"}:
        args.append(f"align: {_TYPST_ALIGN[align]}")  # type: ignore[index]
    if args:
        return f"table.cell({', '.join(args)}){body}"
    return body


class TypstWriteError(RuntimeError):
    """Raised when an IR node type has no Typst emitter registered."""

    def __init__(self, node: object, *, detail: str = "") -> None:
        suffix = f" ({detail})" if detail else ""
        super().__init__(
            f"No Typst emitter registered for IR node {type(node).__name__!r}"
            f"{suffix} (backend: typst)."
        )
        self.node = node


# --------------------------------------------------------------------------- #
# Module-level helpers
# --------------------------------------------------------------------------- #


def _typst_color(value: object, fallback: str = "808080") -> str:
    """Return a Typst ``rgb("#rrggbb")`` expression from a hex colour string."""
    text = str(value or "").strip().lstrip("#")
    if not text:
        text = fallback
    return f'rgb("#{text}")'


def _callout_icon(cfg: dict[str, object]) -> str:
    """Return the callout icon followed by a thin space (empty when unset)."""
    icon = str(cfg.get("icon") or "").strip()
    return f"{icon}#h(0.4em)" if icon else ""


def _callout_fancy(title: str, body: str, cfg: dict[str, object]) -> str:
    """Coloured callout with an icon header (mirrors the LaTeX 'fancy' style)."""
    border = _typst_color(cfg.get("border_color"))
    title_color = _typst_color(cfg.get("title_color", cfg.get("border_color")))
    header = f"{_callout_icon(cfg)}{title}".strip() or title
    inner = _indent(body, "    ")
    return (
        f"#block(width: 100%, radius: 2pt, "
        f"stroke: (left: 1.5pt + {border}, rest: 0.4pt + {border}))[\n"
        f"  #block(width: 100%, fill: {border}.lighten(90%), inset: (x: 8pt, y: 4pt))"
        f'[#text(weight: "bold", fill: {title_color})[{header}]]\n'
        f"  #block(width: 100%, inset: (x: 8pt, y: 6pt))[\n{inner}\n  ]\n"
        f"]"
    )


def _callout_classic(title: str, body: str, cfg: dict[str, object]) -> str:
    """Monochrome callout with a left rule and an icon header ('classic')."""
    header = f"{_callout_icon(cfg)}{title}".strip()
    head_line = f'#text(weight: "bold")[{header}]\n\n' if header else ""
    inner = _indent(f"{head_line}{body}", "  ")
    return (
        "#block(width: 100%, inset: (left: 10pt, rest: 6pt), "
        "stroke: (left: 1.2pt + luma(40%)))[\n"
        f"{inner}\n]"
    )


def _callout_minimal(title: str, body: str, _cfg: dict[str, object]) -> str:
    """Border-only callout, no icon, uppercase bold label ('minimal')."""
    label = f'#text(weight: "bold")[#upper[{title}]]\n\n' if title else ""
    inner = _indent(f"{label}{body}", "  ")
    return f"#block(width: 100%, radius: 1pt, inset: 8pt, stroke: 0.5pt + black)[\n{inner}\n]"


def _in_separator_row(cell: object) -> bool:
    """True when ``cell`` lives in a ``data-ts-role="separator"`` row."""
    from texsmith.extensions.tables.constants import TableAttr

    row = cell.find_parent("tr")  # type: ignore[attr-defined]
    return row is not None and row.get(TableAttr.ROLE) == "separator"


def _escape_string(text: str) -> str:
    """Escape a Typst string literal (used inside ``"…"``)."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _fence_for(body: str) -> str:
    """Pick a backtick fence longer than any run of backticks in ``body``."""
    longest = 0
    run = 0
    for char in body:
        if char == "`":
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return "`" * max(3, longest + 1)


def _raw_inline(text: str) -> str:
    """Render inline raw text with a backtick fence that survives the content."""
    longest = 0
    run = 0
    for char in text:
        if char == "`":
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    fence = "`" * max(1, longest + 1)
    # A leading/trailing space is needed when the content starts/ends with a
    # backtick so Typst does not merge the fences.
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def _indent(text: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" if line else line for line in text.split("\n"))


# Typst has no \LaTeX-style logo macros; render the common logos as plain text.
_TEXLOGO_TEXT = {
    "tex": "TeX",
    "latex": "LaTeX",
    "latex2e": "LaTeX2e",
}

_LABEL_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:-]")


# Equation cross-references / labels are handled outside ``mitex`` (see ``_mitex``).
_PURE_EQREF_RE = re.compile(r"^\s*\\(?:eqref|ref)\s*\{([^}]*)\}\s*$")
_LABEL_RE = re.compile(r"\\label\s*\{([^}]*)\}")

_INLINE_MATH_RE = re.compile(r"^\s*(?:\$(?P<dollar>.+)\$|\\\((?P<paren>.+)\\\))\s*$", re.DOTALL)


def _latex_inline_math_payload(text: str) -> str | None:
    """Return the math body of a ``$…$`` / ``\\(…\\)`` latex raw inline (else None)."""
    match = _INLINE_MATH_RE.match(text)
    if not match:
        return None
    return (match.group("dollar") or match.group("paren") or "").strip()


def citation_label(key: str) -> str:
    """Map a bibliography key to a Typst label (``<...>``).

    Typst label syntax forbids whitespace and most punctuation; bibliography
    keys are sanitised the same way the ``.bib`` is normalised so ``@key`` and
    ``<key>`` agree.
    """
    return _LABEL_SAFE_RE.sub("-", key.strip())


__all__ = ["TypstWriteError", "TypstWriter", "citation_label"]
