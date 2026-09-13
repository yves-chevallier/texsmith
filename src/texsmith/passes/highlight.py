"""The ``highlight`` pass: Pygments highlighting for the LaTeX backend (decision X3).

Last before ``write``, LaTeX only, when ``code.engine`` is ``pygments``
(the default) — or ``minted``, for inline code alone:

* a :class:`~texsmith.ir.model.CodeBlock` becomes ``Div{name="code"}`` with
  the fence options as attributes (``lang``, ``title``, ``linenums``,
  ``hl_lines``, ``id``, ``stretch`` — ``0.5`` for box-drawing art, the
  writer's heuristic — plus ``engine=pygments``) and one
  ``RawBlock{format="latex"}`` child holding the Pygments ``LatexFormatter``
  output: a ``Verbatim`` environment with ``breaklines, breakanywhere,
  commandchars=\\\\\\{\\}`` and ``highlightlines`` (``pygments.py``). The Rust
  writer serialises the ``tscode`` keys from the ``Div`` exactly as for a
  ``CodeBlock`` and prints the raw body; a ``Listing:`` caption still pairs
  with it. The ``Div`` keeps the block's id and span (span rule 1).
* a :class:`~texsmith.ir.model.Code` span with a language becomes
  ``RawInline{latex, "{\\ttfamily …}"}`` with ``\\allowbreak{}`` after each
  ``code.inline.breaks`` character (``add_break_points``); under ``minted`` it
  becomes ``\\mintinline[breaklines=true]{lang}|…|`` with the first delimiter
  absent from the text (``writer.py``); ``code.inline.plain`` and a span
  without language leave the node to the writer's ``\\tscodeinline``.

The style definitions Pygments needs go to ``ctx.pygments_styles`` (keyed as
``PygmentsLatexHighlighter.style_key``); the pipeline copies them into
``DocumentState.pygments_styles`` for ``ts-code`` and requires that fragment.
The slot bodies computed by ``slots`` are rewritten alongside ``ir`` so both
name the same nodes.
"""

from __future__ import annotations

from dataclasses import replace
import re
from typing import TYPE_CHECKING

from texsmith.adapters.latex.pygments import PygmentsLatexHighlighter
from texsmith.core.code_options import CODE_ENGINES, normalise_inline_options
from texsmith.core.coerce import coerce_bool
from texsmith.ir import model
from texsmith.ir.walk import map_tree
from texsmith.passes import PassContext, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


__all__ = ["code_engine", "highlight_lines", "run"]

_ASCII_ART = frozenset("┌┬─┐│├┼┤└┴┘")
#: ``writer.py``: the first one absent from the text delimits ``\mintinline``.
_MINTED_DELIMITERS = ("|", "!", ";", ":", "+", "/", "-", "=", "~", "*", "#", "?")
_RANGE = re.compile(r"^(\d+)(?:-(\d+))?$")
_SKIPPED_KEYS = frozenset({"lang", "include", "engine"})


def code_engine(code: object) -> str:
    """The engine named by a ``code`` section (mapping or bare string), ``pygments`` by default."""
    value = code.get("engine") if isinstance(code, dict) else code
    engine = str(value or "pygments").strip().lower()
    return engine if engine in CODE_ENGINES else "pygments"


def highlight_lines(value: str | None) -> list[int]:
    """The line numbers of an ``hl_lines`` option: ``"2-3 5"`` → ``[2, 3, 5]``."""
    lines: list[int] = []
    for token in re.split(r"[\s,]+", value or ""):
        match = _RANGE.match(token)
        if match is None:
            continue
        start = int(match.group(1))
        end = int(match.group(2) or start)
        lines.extend(range(start, end + 1))
    return lines


def _linenums(value: str | None) -> bool:
    """``linenums`` is on unless it spells a false: a number is a start line."""
    return value is not None and coerce_bool(value) is not False


def _option(attrs: model.Attrs, key: str) -> str | None:
    for name, value in attrs.kv:
        if name == key:
            return value
    return None


def _minted_delimiter(text: str) -> str | None:
    for delimiter in _MINTED_DELIMITERS:
        if delimiter not in text:
            return delimiter
    return None


class _Highlighter:
    __slots__ = ("breaks", "ctx", "engine", "plain", "pygments")

    def __init__(self, ctx: PassContext) -> None:
        self.ctx = ctx
        code = dict(ctx.code)
        self.engine = code_engine(code)
        inline = normalise_inline_options(code.get("inline"))
        self.plain = bool(inline["plain"])
        self.breaks = str(inline["breaks"])
        style = str(code.get("style") or "bw").strip() or "bw"
        self.pygments = PygmentsLatexHighlighter(style=style)

    def _record_styles(self, definitions: str) -> None:
        if definitions:
            self.ctx.pygments_styles.setdefault(self.pygments.style_key, definitions)

    def block(self, node: model.CodeBlock) -> model.Block:
        options = node.options
        lang = node.lang or _option(options, "lang") or "text"
        latex, definitions = self.pygments.render(
            node.text,
            lang,
            linenos=_linenums(_option(options, "linenums")),
            highlight_lines=highlight_lines(_option(options, "hl_lines")),
        )
        self._record_styles(definitions)
        kv: list[tuple[str, str]] = [("lang", lang)]
        kv.extend(item for item in options.kv if item[0] not in _SKIPPED_KEYS)
        if _option(options, "stretch") is None and any(ch in _ASCII_ART for ch in node.text):
            kv.append(("stretch", "0.5"))
        kv.append(("engine", "pygments"))
        payload = model.RawBlock(format="latex", text=latex, id=self.ctx.ids.next(), span=node.span)
        return model.Div(
            name="code",
            attrs=replace(options, kv=tuple(kv)),
            content=(payload,),
            id=node.id,
            span=node.span,
        )

    def inline(self, node: model.Code) -> model.Inline:
        lang = (node.lang or "").strip()
        if not lang or self.plain:
            return node
        if self.engine == "minted":
            delimiter = _minted_delimiter(node.text)
            if delimiter is None:
                return node
            text = f"\\mintinline[breaklines=true]{{{lang}}}{delimiter}{node.text}{delimiter}"
            return model.RawInline(format="latex", text=text, id=node.id, span=node.span)
        latex, definitions = self.pygments.render_inline(node.text, lang)
        self._record_styles(definitions)
        latex = self.pygments.add_break_points(latex.rstrip("\n"), self.breaks)
        return model.RawInline(
            format="latex", text="{\\ttfamily " + latex + "}", id=node.id, span=node.span
        )

    def visit(self, node: model.Node) -> model.Node:
        if isinstance(node, model.CodeBlock) and self.engine == "pygments":
            return self.block(node)
        if isinstance(node, model.Code):
            return self.inline(node)
        return node


@spec("highlight", stage="post", after=("slots", "headings"))
def run(document: Document, ctx: PassContext) -> Document:
    ir = document.ir
    if ir is None or ctx.backend != "latex":
        return document
    engine = code_engine(dict(ctx.code))
    if engine not in ("pygments", "minted"):
        return document

    highlighter = _Highlighter(ctx)
    rebuilt = map_tree(ir, highlighter.visit)
    if rebuilt is ir:
        return document

    # The bodies are slices of ``ir.blocks``: rewrite them to the same nodes.
    mapping = {id(old): new for old, new in zip(ir.blocks, rebuilt.blocks, strict=True)}
    bodies = tuple(
        replace(body, blocks=tuple(mapping.get(id(block), block) for block in body.blocks))
        for body in document.bodies
    )
    return document.evolve(ir=rebuilt, bodies=bodies)
