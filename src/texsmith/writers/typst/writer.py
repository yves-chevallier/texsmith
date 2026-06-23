"""``TypstWriter`` — emit Typst markup from the TeXSmith IR.

This is the project's *second* backend: it consumes the **same** IR the LaTeX
writer does (``readers/`` and ``ir/`` are untouched), proving the architecture
pays off. The writer is a typed visitor over :mod:`texsmith.ir`; each covered
node class has an emitter registered with the shared
:func:`~texsmith.writers.registry.writes` decorator and dispatch is keyed by
node class along the MRO.

Coverage spans a real templated document (article + book): Document, Para/Plain,
Header, all inline emphasis (Emph/Strong/Strikeout/Underline/Highlight/SmallCaps/
Sub/Superscript/Quoted), Code/CodeBlock, Math, Link, Cite, Note (footnote),
IndexEntry, TexLogo, Keystroke, Span (footnote-ref/abbr/label + transparent),
Bullet/OrderedList, DefinitionList, BlockQuote, Admonition, Div, HorizontalRule,
Image, Figure, and simple (GFM) Table. Any IR node without a Typst emitter raises
:class:`TypstWriteError` — an explicit, localised error naming the node type and
the backend, mirroring the LaTeX backend's ``LaTeXWriteError``. Rich
(yaml/data-ts) tables remain out of the covered subset.

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
        """Render TeX math source via the ``mitex`` package."""
        self.state.runtime["uses_mitex"] = True
        fence = _fence_for(tex)
        if display:
            return f"#mitex({fence}{tex}{fence})"
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
        return self._inlines(node.content).strip()

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
        body = _indent(self._join_blocks(node.content), "  ")
        header = f"  [*{title}*]\n" if title else ""
        # A simple bordered block: faithful enough for callouts without a
        # callout theme system (which the Typst backend has no counterpart for).
        return f"#block(stroke: 0.5pt, inset: 8pt, radius: 2pt, width: 100%)[\n{header}{body}\n]"

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
        return "".join(f"#cite(<{_citation_label(key)}>)" for key in keys)

    # -- table -------------------------------------------------------------

    def _table_call(self, node: ir.Table) -> str:
        """Return a bare ``table(...)`` call (no leading ``#``, no caption)."""
        from texsmith.extensions.tables import schema as tbl

        if node.env or node.colspec:
            # Rich (yaml/data-ts) tables carry pre-computed LaTeX layout; they
            # are not part of the covered Typst subset.
            raise TypstWriteError(node, detail="rich (yaml/data-ts) tables")

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


_TYPST_ALIGN = {"l": "left", "c": "center", "r": "right", "j": "left"}


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


def _find_image(blocks: Sequence[ir.Block]) -> ir.Image | None:
    from texsmith.ir.visitor import walk

    for block in blocks:
        for node in walk(block):
            if isinstance(node, ir.Image):
                return node
    return None


def _find_table(blocks: Sequence[ir.Block]) -> ir.Table | None:
    from texsmith.ir.visitor import walk

    for block in blocks:
        for node in walk(block):
            if isinstance(node, ir.Table):
                return node
    return None


# Typst has no \LaTeX-style logo macros; render the common logos as plain text.
_TEXLOGO_TEXT = {
    "tex": "TeX",
    "latex": "LaTeX",
    "latex2e": "LaTeX2e",
}

_DOI_KEY_PATTERN = r"10\.\d{4,9}/[^\s,\]]+"
_DOI_KEY_RE = re.compile(rf"^{_DOI_KEY_PATTERN}$")
_CITATION_KEY_PATTERN = rf"(?:{_DOI_KEY_PATTERN}|[A-Za-z0-9_\-:]+)"
_CITATION_PAYLOAD_RE = re.compile(
    rf"^\s*({_CITATION_KEY_PATTERN}(?:\s*,\s*{_CITATION_KEY_PATTERN})*)\s*$"
)
_LABEL_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:-]")


def _normalise_footnote_id(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if ":" in text:
        prefix, suffix = text.split(":", 1)
        if prefix.startswith("fnref") or prefix.startswith("fn"):
            return suffix
    return text


def _is_doi_key(candidate: str) -> bool:
    return bool(_DOI_KEY_RE.match(candidate.strip()))


def _split_citation_keys(identifier: str) -> list[str]:
    if not identifier:
        return []
    if "," not in identifier:
        return [identifier.strip()] if _is_doi_key(identifier) else []
    return [part.strip() for part in identifier.split(",") if part.strip()]


def _citation_keys_from_payload(text: str | None) -> list[str]:
    """Citation keys when a footnote body is just a key list (else empty)."""
    if not text:
        return []
    match = _CITATION_PAYLOAD_RE.match(text)
    if not match:
        return []
    return [key.strip() for key in match.group(1).split(",") if key.strip()]


_INLINE_MATH_RE = re.compile(r"^\s*(?:\$(?P<dollar>.+)\$|\\\((?P<paren>.+)\\\))\s*$", re.DOTALL)


def _latex_inline_math_payload(text: str) -> str | None:
    """Return the math body of a ``$…$`` / ``\\(…\\)`` latex raw inline (else None)."""
    match = _INLINE_MATH_RE.match(text)
    if not match:
        return None
    return (match.group("dollar") or match.group("paren") or "").strip()


def _citation_label(key: str) -> str:
    """Map a bibliography key to a Typst label (``<...>``).

    Typst label syntax forbids whitespace and most punctuation; bibliography
    keys are sanitised the same way the ``.bib`` is normalised so ``@key`` and
    ``<key>`` agree.
    """
    return _LABEL_SAFE_RE.sub("-", key.strip())


__all__ = ["TypstWriteError", "TypstWriter"]
