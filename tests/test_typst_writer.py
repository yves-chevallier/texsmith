"""Unit tests for the IR→Typst writer (Phase 4).

One case per covered node type: a hand-written IR fixture is emitted and the
resulting Typst string asserted. Uncovered nodes must raise a clear, localised
:class:`TypstWriteError`. A final case round-trips a real GFM table through the
production reader so the model-backed table path is exercised end to end.
"""

from __future__ import annotations

import pytest

from texsmith.ir import nodes as ir
from texsmith.readers.html import HtmlReader
from texsmith.writers.typst import (
    TypstWriteError,
    TypstWriter,
    TypstWriterState,
    escape_typst_chars,
    render_document,
    writes,
)


def emit(node: ir.Node) -> str:
    return TypstWriter(TypstWriterState()).emit(node)


def write_doc(*blocks: ir.Block) -> str:
    return TypstWriter(TypstWriterState()).write(ir.Document(content=tuple(blocks)))


# --------------------------------------------------------------------------- #
# Inline nodes
# --------------------------------------------------------------------------- #


def test_str_is_escaped() -> None:
    assert emit(ir.Str("a*b_c#d")) == "a\\*b\\_c\\#d"


def test_space_and_breaks() -> None:
    assert emit(ir.Space()) == " "
    assert emit(ir.SoftBreak()) == "\n"
    assert emit(ir.LineBreak()) == " \\\n"


def test_emph_strong_strikeout() -> None:
    assert emit(ir.Emph(content=(ir.Str("x"),))) == "_x_"
    assert emit(ir.Strong(content=(ir.Str("x"),))) == "*x*"
    assert emit(ir.Strikeout(content=(ir.Str("x"),))) == "#strike[x]"


def test_inline_code_raw() -> None:
    assert emit(ir.Code(text="a + b")) == "`a + b`"
    # A backtick inside the code forces a longer fence with padding.
    assert emit(ir.Code(text="a`b")) == "``a`b``"


def test_math_inline_and_display() -> None:
    # Math carries TeX source; the Typst backend renders it via the ``mitex``
    # LaTeX-math package (inline -> #mi, display -> #mitex).
    assert emit(ir.Math(text="x^2", display=False)) == "#mi(```x^2```)"
    assert emit(ir.Math(text="E = m c^2", display=True)) == "#mitex(```E = m c^2```)"


def test_latex_inline_math_raw_inline_via_mitex() -> None:
    # The reader encodes math typed in text as a latex RawInline; recover it.
    assert emit(ir.RawInline(format="latex", text="$E$")) == "#mi(```E```)"
    assert emit(ir.RawInline(format="latex", text=r"\(a+b\)")) == "#mi(```a+b```)"
    # Non-math latex raw inline is still dropped (backend-scoped escape hatch).
    assert emit(ir.RawInline(format="latex", text=r"\textbf{x}")) == ""


def test_link() -> None:
    node = ir.Link(content=(ir.Str("site"),), target="https://example.com")
    assert emit(node) == '#link("https://example.com")[site]'


def test_image() -> None:
    assert emit(ir.Image(src="a.png")) == '#image("a.png")'
    assert emit(ir.Image(src="a.png", width="50%")) == '#image("a.png", width: 50%)'


def test_raw_inline_is_backend_scoped() -> None:
    assert emit(ir.RawInline(format="typst", text="#sym.alpha")) == "#sym.alpha"
    # A LaTeX escape hatch is ignored by the Typst backend (per the IR contract).
    assert emit(ir.RawInline(format="latex", text="\\alpha")) == ""


# --------------------------------------------------------------------------- #
# Block nodes
# --------------------------------------------------------------------------- #


def test_para_and_plain() -> None:
    assert emit(ir.Para(content=(ir.Str("hi"),))) == "hi"
    assert emit(ir.Plain(content=(ir.Str("hi"),))) == "hi"


def test_header_levels() -> None:
    assert emit(ir.Header(level=1, content=(ir.Str("Top"),))) == "= Top"
    assert emit(ir.Header(level=3, content=(ir.Str("Sub"),))) == "=== Sub"


def test_code_block() -> None:
    out = emit(ir.CodeBlock(text="print(1)\n", lang="python"))
    assert out == "```python\nprint(1)\n```"
    # No language -> bare fence.
    assert emit(ir.CodeBlock(text="x", lang="text")) == "```\nx\n```"


def test_blockquote() -> None:
    node = ir.BlockQuote(content=(ir.Para(content=(ir.Str("q"),)),))
    assert emit(node) == "#quote(block: true)[\n  q\n]"


def test_bullet_and_ordered_lists() -> None:
    items = ((ir.Plain(content=(ir.Str("a"),)),), (ir.Plain(content=(ir.Str("b"),)),))
    assert emit(ir.BulletList(items=items)) == "- a\n- b"
    assert emit(ir.OrderedList(items=items)) == "+ a\n+ b"


def test_nested_list_is_indented() -> None:
    nested = ir.BulletList(items=((ir.Plain(content=(ir.Str("inner"),)),),))
    outer = ir.BulletList(
        items=((ir.Para(content=(ir.Str("outer"),)), nested),),
    )
    assert emit(outer) == "- outer\n  - inner"


def test_horizontal_rule() -> None:
    assert emit(ir.HorizontalRule()) == "#line(length: 100%)"


def test_figure_with_image_and_caption() -> None:
    fig = ir.Figure(
        content=(ir.Plain(content=(ir.Image(src="a.png"),)),),
        caption=(ir.Str("A cap"),),
    )
    out = emit(fig)
    # Within a figure the image must be a bare expression (no leading hash).
    assert 'image("a.png")' in out
    assert "#figure(" in out
    assert "caption: [A cap]" in out


def test_raw_block_is_backend_scoped() -> None:
    assert emit(ir.RawBlock(format="typst", text="#pagebreak()")) == "#pagebreak()"
    assert emit(ir.RawBlock(format="latex", text="\\clearpage")) == ""


# --------------------------------------------------------------------------- #
# Tables (model-backed, via the production reader)
# --------------------------------------------------------------------------- #


def test_simple_gfm_table() -> None:
    html = (
        "<table><thead><tr><th>A</th><th>B</th></tr></thead>"
        "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
    )
    doc = HtmlReader().read(html)
    table = doc.content[0]
    assert isinstance(table, ir.Table)
    out = emit(table)
    assert out.startswith("#table(")
    assert "columns: 2," in out
    assert "table.header([A], [B])," in out
    assert "[1], [2]," in out


def test_rich_table_raises() -> None:
    html = (
        "<table><thead><tr><th>A</th><th>B</th></tr></thead>"
        "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
    )
    plain = HtmlReader().read(html).content[0]
    assert isinstance(plain, ir.Table)
    # Promote it to a "rich" table by attaching pre-computed layout strings.
    node = ir.Table(model=plain.model, cells=plain.cells, env="tabular", colspec="ll")
    with pytest.raises(TypstWriteError, match="rich"):
        emit(node)


# --------------------------------------------------------------------------- #
# Document, errors, escaping, registry
# --------------------------------------------------------------------------- #


def test_document_joins_blocks_with_blank_lines() -> None:
    out = write_doc(
        ir.Header(level=1, content=(ir.Str("T"),)),
        ir.Para(content=(ir.Str("body"),)),
    )
    assert out == "= T\n\nbody"


def test_uncovered_node_raises_localised_error() -> None:
    with pytest.raises(TypstWriteError, match=r"MarginNote.*typst"):
        emit(ir.MarginNote(content=(ir.Para(content=(ir.Str("m"),)),)))


def test_escaper_escapes_markup_specials() -> None:
    assert escape_typst_chars("# * _ ` < > @ [ ] $ \\") == (
        "\\# \\* \\_ \\` \\< \\> \\@ \\[ \\] \\$ \\\\"
    )


def test_render_document_wraps_body_with_title() -> None:
    out = render_document("= Hi", title="My Title")
    assert "My Title" in out
    assert out.rstrip().endswith("= Hi")
    assert "#set page" in out


# --------------------------------------------------------------------------- #
# Templated-document nodes (article + book coverage)
# --------------------------------------------------------------------------- #


def test_inline_emphasis_variants() -> None:
    assert emit(ir.Underline(content=(ir.Str("u"),))) == "#underline[u]"
    assert emit(ir.Highlight(content=(ir.Str("h"),))) == "#highlight[h]"
    assert emit(ir.SmallCaps(content=(ir.Str("s"),))) == "#smallcaps[s]"
    assert emit(ir.Subscript(content=(ir.Str("2"),))) == "#sub[2]"
    assert emit(ir.Superscript(content=(ir.Str("3"),))) == "#super[3]"


def test_quoted_uses_smartquotes() -> None:
    assert emit(ir.Quoted(content=(ir.Str("hi"),))) == '"hi"'


def test_cite_emits_native_marker_and_records() -> None:
    state = TypstWriterState()
    writer = TypstWriter(state)
    out = writer.emit(ir.Cite(keys=("Smith2020", "Doe2021")))
    assert out == "#cite(<Smith2020>)#cite(<Doe2021>)"
    assert state.citations == ["Smith2020", "Doe2021"]


def test_note_emits_footnote() -> None:
    note = ir.Note(content=(ir.Para(content=(ir.Str("body"),)),))
    assert emit(note) == "#footnote[body]"


def test_texlogo_renders_plain_text() -> None:
    assert emit(ir.TexLogo(name="latex")) == "LaTeX"
    assert emit(ir.TexLogo(name="tex")) == "TeX"


def test_index_entry_surfaces_visible_text_only() -> None:
    assert emit(ir.IndexEntry(path=("Topic",), visible=(ir.Str("Topic"),))) == "Topic"
    assert emit(ir.IndexEntry(path=("Hidden",))) == ""


def test_definition_list() -> None:
    item = ir.DefinitionItem(
        term=(ir.Str("Term"),),
        definitions=((ir.Para(content=(ir.Str("Meaning"),)),),),
    )
    assert emit(ir.DefinitionList(items=(item,))) == "/ Term: Meaning"


def test_admonition_renders_titled_block() -> None:
    adm = ir.Admonition(
        kind="note",
        title=(ir.Str("Heads up"),),
        content=(ir.Para(content=(ir.Str("body"),)),),
    )
    out = emit(adm)
    assert "#block(" in out
    assert "*Heads up*" in out
    assert "body" in out


def test_footnote_ref_resolves_to_citation_when_in_bibliography() -> None:
    state = TypstWriterState(bibliography=frozenset({"Smith2020"}))
    writer = TypstWriter(state)
    span = ir.Span(
        content=(ir.Str("1"),),
        attrs=(("role", "footnote-ref"), ("ref", "Smith2020")),
    )
    assert writer.emit(span) == "#cite(<Smith2020>)"
    assert state.citations == ["Smith2020"]


def test_footnote_ref_resolves_to_footnote_when_body_present() -> None:
    doc = ir.Document(
        content=(
            ir.Para(
                content=(
                    ir.Span(
                        content=(ir.Str("1"),),
                        attrs=(("role", "footnote-ref"), ("ref", "fn1")),
                    ),
                )
            ),
            ir.Div(
                content=(ir.Para(content=(ir.Str("the footnote body"),)),),
                attrs=(("role", "footnote-def"), ("id", "fn1")),
            ),
        )
    )
    out = TypstWriter(TypstWriterState()).write(doc)
    assert "#footnote[the footnote body]" in out


def test_div_footnote_containers_emit_nothing() -> None:
    div = ir.Div(
        content=(ir.Para(content=(ir.Str("x"),)),),
        attrs=(("role", "footnotes"),),
    )
    assert emit(div) == ""


def test_abbr_records_description_and_renders_term() -> None:
    state = TypstWriterState()
    writer = TypstWriter(state)
    span = ir.Span(
        content=(ir.Str("HTML"),),
        attrs=(("role", "abbr"), ("title", "HyperText Markup Language")),
    )
    assert writer.emit(span) == "HTML"
    assert state.abbreviations["HTML"] == "HyperText Markup Language"


def test_heading_offset_applies() -> None:
    state = TypstWriterState(heading_offset=-1)
    out = TypstWriter(state).emit(ir.Header(level=2, content=(ir.Str("Chapter"),)))
    assert out == "= Chapter"


def test_registry_is_extensible_via_subclass() -> None:
    class CustomWriter(TypstWriter):
        @writes(ir.MarginNote)
        def _margin(self, node: ir.MarginNote) -> str:
            return "#note[custom]"

    out = CustomWriter(TypstWriterState()).emit(
        ir.MarginNote(content=(ir.Para(content=(ir.Str("m"),)),))
    )
    assert out == "#note[custom]"
