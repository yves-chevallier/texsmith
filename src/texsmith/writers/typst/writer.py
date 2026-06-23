"""``TypstWriter`` — emit Typst markup from the TeXSmith IR.

This is the project's *second* backend: it consumes the **same** IR the LaTeX
writer does (``readers/`` and ``ir/`` are untouched), proving the architecture
pays off. The writer is a typed visitor over :mod:`texsmith.ir`; each covered
node class has an emitter registered with the shared
:func:`~texsmith.writers.registry.writes` decorator and dispatch is keyed by
node class along the MRO.

Coverage is a deliberate *subset* sufficient for a real, simple document
(Document, Para/Plain, Header, Str/Space/SoftBreak/LineBreak,
Emph/Strong/Strikeout, Code/CodeBlock, Math, Link, Bullet/OrderedList,
BlockQuote, HorizontalRule, Image, Figure, simple Table). Any IR node without a
Typst emitter raises :class:`TypstWriteError` — an explicit, localised error
naming the node type and the backend (no silent drop, no misleading empty
output), mirroring the LaTeX backend's ``LaTeXWriteError``.

Math note: the IR carries *TeX* math source (``Math.text``). Typst has its own
native math syntax, so faithful TeX→Typst math translation is out of scope; the
source is emitted verbatim inside Typst's ``$…$`` delimiters (correct for the
TeX/Typst-compatible subset, e.g. ``x^2``, ``a + b``).
"""

from __future__ import annotations

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
        return self._join_blocks(document.content)

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

    @writes(ir.Code)
    def _code(self, node: ir.Code) -> str:
        # Inline raw text; pick a backtick fence longer than any run inside.
        return _raw_inline(node.text)

    @writes(ir.Math)
    def _math(self, node: ir.Math) -> str:
        payload = node.text.strip()
        if node.display:
            return f"$ {payload} $"
        return f"${payload}$"

    @writes(ir.Link)
    def _link(self, node: ir.Link) -> str:
        target = node.target
        body = self._inlines(node.content)
        if not body:
            return f'#link("{_escape_string(target)}")'
        return f'#link("{_escape_string(target)}")[{body}]'

    @writes(ir.Image)
    def _image(self, node: ir.Image) -> str:
        return _image_call(node)

    @writes(ir.RawInline)
    def _raw_inline(self, node: ir.RawInline) -> str:
        # Per the IR contract, a raw escape hatch is emitted only for its own
        # backend and ignored otherwise (not an error: it is *defined* to be
        # backend-scoped). ``typst`` raw payloads pass through verbatim.
        return node.text if node.format == "typst" else ""

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
        marker = "=" * max(1, node.level)
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
        image = _find_image(node.content)
        caption = self._inlines(node.caption).strip() if node.caption else ""
        body = _image_call(image) if image is not None else self._join_blocks(node.content)
        if caption:
            return f"#figure(\n  {body},\n  caption: [{caption}],\n)"
        return f"#figure(\n  {body},\n)"

    @writes(ir.Table)
    def _table(self, node: ir.Table) -> str:
        return self._render_table(node)

    @writes(ir.RawBlock)
    def _raw_block(self, node: ir.RawBlock) -> str:
        return node.text if node.format == "typst" else ""

    @writes(ir.Document)
    def _document(self, node: ir.Document) -> str:
        return self._join_blocks(node.content)

    # -- table -------------------------------------------------------------

    def _render_table(self, node: ir.Table) -> str:
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
            "#table(",
            f"  columns: {n_cols},",
            f"  align: ({', '.join(aligns)}),",
            "  table.header(" + ", ".join(f"[{c}]" for c in header) + "),",
        ]
        for row in rows:
            lines.append("  " + ", ".join(f"[{c}]" for c in row) + ",")
        caption = self._inlines(node.caption).strip() if node.caption else ""
        table_call = "\n".join(lines) + "\n)"
        if caption:
            return f"#figure(\n  {_indent(table_call, '  ').lstrip()},\n  caption: [{caption}],\n)"
        return table_call


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


def _image_call(node: ir.Image) -> str:
    parts = [f'image("{_escape_string(node.src)}")']
    if node.width:
        parts = [f'image("{_escape_string(node.src)}", width: {node.width})']
    call = parts[0]
    return f"#{call}"


def _indent(text: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" if line else line for line in text.split("\n"))


def _find_image(blocks: Sequence[ir.Block]) -> ir.Image | None:
    from texsmith.ir.visitor import walk

    for block in blocks:
        for node in walk(block):
            if isinstance(node, ir.Image):
                return node
    return None


__all__ = ["TypstWriteError", "TypstWriter"]
