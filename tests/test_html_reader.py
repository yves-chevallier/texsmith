"""Unit tests for the HTML → IR reader on the generated models (plan task 3.8).

One case per node type / handler: a hand-written HTML fixture is lowered and the
resulting IR is asserted structurally against :mod:`texsmith.ir.model` — the
shapes ``tmark.parse`` gives the same constructs. A final integration test runs
real Markdown through the production adapter and checks that no construct is
dropped silently.
"""

from __future__ import annotations

from texsmith.diagnostics import Diagnostic
from texsmith.ir import model as ir
from texsmith.ir.walk import walk
from texsmith.readers.html import HtmlReader, ReaderRegistry, ReadLevel, reads


def read(html: str) -> ir.Document:
    return HtmlReader().read(html)


def only_block(html: str) -> ir.Block:
    doc = read(html)
    assert len(doc.blocks) == 1, doc.blocks
    return doc.blocks[0]


def first_para_inlines(html: str) -> tuple[ir.Inline, ...]:
    block = only_block(html)
    assert isinstance(block, ir.Para)
    return block.content


def kv(attrs: ir.Attrs) -> dict[str, str]:
    return dict(attrs.kv)


# ---------------------------------------------------------------------------
# Text / whitespace
# ---------------------------------------------------------------------------


def test_text_keeps_whitespace_inside_str() -> None:
    inlines = first_para_inlines("<p>hello world</p>")
    assert inlines == (ir.Str("hello world"),)


def test_leading_trailing_space_stripped_in_paragraph() -> None:
    inlines = first_para_inlines("<p>  spaced  </p>")
    assert inlines == (ir.Str("spaced"),)


def test_soft_line_wrap_is_a_soft_break() -> None:
    inlines = first_para_inlines("<p>one\n    two</p>")
    assert inlines == (ir.Str("one"), ir.SoftBreak(), ir.Str("two"))


def test_space_around_inline_nodes_is_kept() -> None:
    inlines = first_para_inlines("<p>a <em>b</em> c</p>")
    assert inlines == (ir.Str("a "), ir.Emph(content=(ir.Str("b"),)), ir.Str(" c"))


def test_ids_are_dense_and_spans_absent() -> None:
    doc = read("<h1>T</h1><p>a <em>b</em></p>")
    ids = [node.id for node in walk(doc)]
    assert sorted(ids) == list(range(1, len(ids) + 1))
    assert all(node.span == ir.NO_SPAN for node in walk(doc))
    assert doc.file == 0
    assert HtmlReader().read("<p>x</p>", file=3).file == 3


# ---------------------------------------------------------------------------
# Inline emphasis family
# ---------------------------------------------------------------------------


def test_emphasis_and_strong() -> None:
    inlines = first_para_inlines("<p><em>a</em><strong>b</strong></p>")
    assert inlines == (
        ir.Emph(content=(ir.Str("a"),)),
        ir.Strong(content=(ir.Str("b"),)),
    )


def test_strikeout_underline_highlight_subscript_superscript_quote() -> None:
    inlines = first_para_inlines(
        "<p><del>d</del><ins>i</ins><mark>m</mark><sub>s</sub><sup>p</sup><q>q</q></p>"
    )
    assert inlines == (
        ir.Strikeout(content=(ir.Str("d"),)),
        ir.Underline(content=(ir.Str("i"),)),
        ir.Highlight(content=(ir.Str("m"),)),
        ir.Subscript(content=(ir.Str("s"),)),
        ir.Superscript(content=(ir.Str("p"),)),
        ir.Quoted(content=(ir.Str("q"),)),
    )


def test_line_break() -> None:
    inlines = first_para_inlines("<p>a<br/>b</p>")
    assert ir.LineBreak() in inlines


def test_smallcaps_span() -> None:
    inlines = first_para_inlines('<p><span class="texsmith-smallcaps">sc</span></p>')
    assert inlines == (ir.SmallCaps(content=(ir.Str("sc"),)),)


def test_bare_span_is_transparent_and_id_span_is_a_host() -> None:
    assert first_para_inlines("<p><span>x</span></p>") == (ir.Str("x"),)
    inlines = first_para_inlines('<p><span id="a" class="c">x</span></p>')
    assert inlines == (ir.SpanNode(attrs=ir.Attrs(classes=("c",), id="a"), content=(ir.Str("x"),)),)


# ---------------------------------------------------------------------------
# Code
# ---------------------------------------------------------------------------


def test_inline_code() -> None:
    inlines = first_para_inlines('<p><code class="language-python">x=1</code></p>')
    assert inlines == (ir.Code(text="x=1", lang="python"),)


def test_inline_code_plain() -> None:
    inlines = first_para_inlines("<p><code>raw</code></p>")
    assert inlines == (ir.Code(text="raw", lang=None),)


def test_code_block_pre() -> None:
    block = only_block('<pre><code class="language-py">print(1)\n</code></pre>')
    assert block == ir.CodeBlock(text="print(1)\n", lang="py")


def test_code_block_highlight_div_with_filename_and_lineno() -> None:
    html = (
        '<div class="highlight">'
        '<span class="filename">main.py</span>'
        '<table class="highlighttable"><tr><td class="linenos">1</td></tr></table>'
        '<code class="language-py">x\n</code></div>'
    )
    block = only_block(html)
    assert isinstance(block, ir.CodeBlock)
    assert block.lang == "py"
    assert kv(block.options) == {"title": "main.py", "linenums": "1"}


def test_mermaid_pre_is_a_generated_image() -> None:
    block = only_block('<pre class="mermaid"><code>graph TD\nA-->B</code></pre>')
    assert isinstance(block, ir.Para)
    (image,) = block.content
    assert isinstance(image, ir.Image)
    assert image.src == ""
    assert kv(image.attrs) == {"generate": "mermaid", "code": "graph TD\nA-->B"}


# ---------------------------------------------------------------------------
# Headings, rules, paragraphs
# ---------------------------------------------------------------------------


def test_heading_with_identifier_and_anchor_dropped() -> None:
    block = only_block('<h2 id="sec">Title<a class="headerlink" href="#sec">¶</a></h2>')
    assert block == ir.Header(level=2, attrs=ir.Attrs(id="sec"), content=(ir.Str("Title"),))


def test_horizontal_rule() -> None:
    assert only_block("<hr/>") == ir.HorizontalRule()


def test_latex_raw_paragraph() -> None:
    block = only_block('<p class="latex-raw">\\foo{bar}</p>')
    assert block == ir.RawBlock(format="latex", text="\\foo{bar}")


def test_data_script_paragraph_and_span() -> None:
    block = only_block('<p data-script="arabics">ألف</p>')
    assert block == ir.Para(
        content=(
            ir.SpanNode(attrs=ir.Attrs(kv=(("script", "arabics"),)), content=(ir.Str("ألف"),)),
        )
    )
    inlines = first_para_inlines('<p>a <span data-script="arabics">ب</span></p>')
    assert inlines[1] == ir.SpanNode(
        attrs=ir.Attrs(kv=(("script", "arabics"),)), content=(ir.Str("ب"),)
    )


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


def test_bullet_list_tight_items_are_plain() -> None:
    block = only_block("<ul><li>a</li><li>b</li></ul>")
    assert block == ir.BulletList(
        items=(
            ir.ListItem(content=(ir.Plain(content=(ir.Str("a"),)),)),
            ir.ListItem(content=(ir.Plain(content=(ir.Str("b"),)),)),
        )
    )


def test_ordered_list_start_and_style() -> None:
    block = only_block('<ol start="3" type="a"><li>x</li></ol>')
    assert isinstance(block, ir.OrderedList)
    assert block.start == 3
    assert block.style is ir.ListStyle.LOWER_ALPHA
    assert only_block("<ol><li>x</li></ol>").start == 1


def test_task_list_marker() -> None:
    block = only_block(
        '<ul><li><input type="checkbox" checked/> done</li>'
        '<li><input type="checkbox"/> open</li></ul>'
    )
    assert isinstance(block, ir.BulletList)
    assert block.items[0] == ir.ListItem(
        content=(ir.Plain(content=(ir.Str("done"),)),), task=ir.Task.DONE
    )
    assert block.items[1].task is ir.Task.OPEN


def test_two_column_list_is_a_multicolumn_div() -> None:
    block = only_block('<ul class="two-column-list"><li>a</li></ul>')
    assert isinstance(block, ir.Div)
    assert block.name == "multicolumn"
    assert kv(block.attrs) == {"cols": "2"}
    assert isinstance(block.content[0], ir.BulletList)


def test_definition_list() -> None:
    block = only_block("<dl><dt>Term</dt><dd>Def</dd></dl>")
    assert block == ir.DefinitionList(
        items=(((ir.Str("Term"),), ((ir.Para(content=(ir.Str("Def"),)),),)),)
    )


# ---------------------------------------------------------------------------
# Blockquote
# ---------------------------------------------------------------------------


def test_blockquote() -> None:
    block = only_block("<blockquote><p>quoted</p></blockquote>")
    assert block == ir.BlockQuote(content=(ir.Para(content=(ir.Str("quoted"),)),))


def test_epigraph_blockquote_carries_class_and_source() -> None:
    block = only_block('<blockquote class="epigraph"><p>q</p><footer>Someone</footer></blockquote>')
    assert block == ir.BlockQuote(
        attrs=ir.Attrs(classes=("epigraph",), kv=(("source", "Someone"),)),
        content=(ir.Para(content=(ir.Str("q"),)),),
    )


def test_blockquote_callout() -> None:
    block = only_block("<blockquote><p>[!warning] Heads up</p><p>body</p></blockquote>")
    assert isinstance(block, ir.Admonition)
    assert block.kind == "warning"
    assert block.title == (ir.Str("Heads up"),)
    assert block.content == (ir.Para(content=(ir.Str("body"),)),)


# ---------------------------------------------------------------------------
# Links / references
# ---------------------------------------------------------------------------


def test_external_link() -> None:
    inlines = first_para_inlines('<p><a href="https://x.io" title="t">go</a></p>')
    assert inlines == (ir.Link(target=ir.Url("https://x.io"), content=(ir.Str("go"),), title="t"),)


def test_anchor_link() -> None:
    inlines = first_para_inlines('<p><a href="#sec">see</a></p>')
    assert inlines == (ir.Link(target=ir.Anchor("sec"), content=(ir.Str("see"),)),)


def test_autoref() -> None:
    inlines = first_para_inlines("<p><autoref identifier='fig:1'>Fig</autoref></p>")
    assert inlines == (ir.Link(target=ir.Anchor("fig:1"), content=(ir.Str("Fig"),)),)


def test_label_only_anchor_is_an_id_span() -> None:
    inlines = first_para_inlines('<p><a id="here"></a>x</p>')
    assert inlines == (ir.SpanNode(attrs=ir.Attrs(id="here")), ir.Str("x"))


# ---------------------------------------------------------------------------
# Footnotes, citations, abbreviations
# ---------------------------------------------------------------------------


def test_footnote_reference_and_definition() -> None:
    doc = read(
        '<p>text<sup id="fnref:note"><a class="footnote-ref" href="#fn:note">1</a></sup></p>'
        '<div class="footnote"><hr/><ol><li id="fn:note"><p>Body&#160;'
        '<a class="footnote-backref" href="#fnref:note">↩</a></p></li></ol></div>'
    )
    assert doc.blocks == (ir.Para(content=(ir.Str("text"), ir.Note(label="note"))),)
    assert doc.footnotes == (
        ir.Footnote(label="note", content=(ir.Para(content=(ir.Str("Body"),)),)),
    )


def test_missing_footnote_is_a_bracketed_ref() -> None:
    inlines = first_para_inlines(
        "<p><texsmith-missing-footnote data-footnote-id='doe2020'></texsmith-missing-footnote></p>"
    )
    assert inlines == (ir.Ref(bracketed=True, items=(ir.RefItem(key="doe2020"),)),)


def test_abbreviation_defines_the_document_abbreviation() -> None:
    doc = read('<p><abbr title="HyperText">HTML</abbr> and <abbr title="x">HTML</abbr></p>')
    assert doc.blocks[0] == ir.Para(
        content=(ir.Abbr(text="HTML"), ir.Str(" and "), ir.Abbr(text="HTML"))
    )
    assert doc.abbreviations == (ir.AbbrDef(expansion="HyperText", key="HTML"),)


def test_abbreviation_without_title_is_plain_text() -> None:
    assert first_para_inlines("<p><abbr>HTML</abbr></p>") == (ir.Str("HTML"),)


def test_critic_deletion_role() -> None:
    inlines = first_para_inlines('<p><del class="critic">gone</del></p>')
    span = inlines[0]
    assert isinstance(span, ir.SpanNode)
    assert kv(span.attrs) == {"role": "critic-deletion"}


# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------


def test_inline_math_arithmatex() -> None:
    inlines = first_para_inlines('<p><span class="arithmatex">\\(a+b\\)</span></p>')
    assert inlines == (ir.Math(text="a+b", display=False),)


def test_inline_math_left_in_text() -> None:
    inlines = first_para_inlines("<p>let $x$ and \\(y\\) be</p>")
    assert inlines == (
        ir.Str("let "),
        ir.Math(text="x"),
        ir.Str(" and "),
        ir.Math(text="y"),
        ir.Str(" be"),
    )


def test_block_math() -> None:
    block = only_block('<div class="arithmatex">\\[E=mc^2\\]</div>')
    assert block == ir.MathBlock(text="E=mc^2")


def test_math_script_display() -> None:
    block = only_block('<script type="math/tex; mode=display">x^2</script>')
    # script is ANY-level; at block level it becomes a Para-wrapped inline.
    assert block == ir.Para(content=(ir.Math(text="x^2", display=True),))


# ---------------------------------------------------------------------------
# Images / figures
# ---------------------------------------------------------------------------


def test_inline_image() -> None:
    inlines = first_para_inlines('<p><img src="a.png" alt="alt" width="50"/></p>')
    assert inlines == (
        ir.Image(src="a.png", alt=(ir.Str("alt"),), attrs=ir.Attrs(kv=(("width", "50"),))),
    )


def test_image_alt_markdown_is_parsed() -> None:
    inlines = first_para_inlines('<p><img src="a.png" alt="anti-*windup*"/></p>')
    assert inlines[0].alt == (ir.Str("anti-"), ir.Emph(content=(ir.Str("windup"),)))


def test_figure_with_caption_is_image_paragraph_then_caption() -> None:
    doc = read('<figure id="f1"><img src="a.png"/><figcaption>Cap</figcaption></figure>')
    assert doc.blocks == (
        ir.Para(content=(ir.Image(src="a.png"),)),
        ir.Caption(kind=ir.CaptionKind.FIGURE, attrs=ir.Attrs(id="f1"), content=(ir.Str("Cap"),)),
    )


def test_figure_without_caption_keeps_its_id_on_the_image() -> None:
    doc = read('<figure id="f1"><img src="a.png"/></figure>')
    assert doc.blocks == (ir.Para(content=(ir.Image(src="a.png", attrs=ir.Attrs(id="f1")),)),)


def test_figure_with_several_images_is_a_figure_container() -> None:
    doc = read(
        '<figure><p><img src="a.png"/></p><p><img src="b.png"/></p>'
        "<figcaption>Both</figcaption></figure>"
    )
    (figure,) = doc.blocks
    assert isinstance(figure, ir.Figure)
    assert [type(block).__name__ for block in figure.content] == ["Para", "Para", "Caption"]


# ---------------------------------------------------------------------------
# Extension constructs
# ---------------------------------------------------------------------------


def test_admonition_div() -> None:
    html = '<div class="admonition note"><p class="admonition-title">Note</p><p>body</p></div>'
    block = only_block(html)
    assert block == ir.Admonition(
        kind="note", title=(ir.Str("Note"),), content=(ir.Para(content=(ir.Str("body"),)),)
    )


def test_details_collapsible_admonition() -> None:
    block = only_block("<details class='tip'><summary>More</summary><p>x</p></details>")
    assert isinstance(block, ir.Admonition)
    assert block.kind == "tip"
    assert kv(block.attrs) == {"collapsed": "true"}
    assert block.title == (ir.Str("More"),)
    opened = only_block("<details class='tip' open><summary>More</summary><p>x</p></details>")
    assert kv(opened.attrs) == {"collapsed": "false"}


def test_marginnote_side() -> None:
    # A margin note is inline-natured: at the top level it is wrapped in a Para.
    inlines = first_para_inlines('<p>x <ts-marginnote data-side="l">hi</ts-marginnote></p>')
    note = inlines[-1]
    assert note == ir.Aside(content=(ir.Plain(content=(ir.Str("hi"),)),), side=ir.Side.LEFT)


def test_progressbar() -> None:
    html = (
        '<div class="progress thin" data-progress-percent="40">'
        '<div class="progress-bar"><p class="progress-label">L</p></div></div>'
    )
    block = only_block(html)
    assert block == ir.Para(
        content=(ir.ProgressBar(value=40.0, attrs=ir.Attrs(classes=("thin",)), label="L"),)
    )


def test_index_entry() -> None:
    html = (
        '<p><span class="ts-hashtag" data-tag="Animal" data-tag1="Cat" data-style="b">'
        "Cat</span></p>"
    )
    inlines = first_para_inlines(html)
    assert inlines == (
        ir.Str("Cat"),
        ir.IndexEntry(main=True, path=((ir.Str("Animal"),), (ir.Str("Cat"),))),
    )


def test_texlogo_is_the_logo_word() -> None:
    inlines = first_para_inlines(
        '<p><span class="tex-logo tex-latex" data-tex-logo="latex">LaTeX</span></p>'
    )
    assert inlines == (ir.Str("LaTeX"),)


def test_keystroke() -> None:
    html = '<p><span class="keys"><kbd class="key-control">Ctrl</kbd><kbd class="key-s">S</kbd></span></p>'
    inlines = first_para_inlines(html)
    assert inlines == (ir.Keystroke(keys=("control", "s")),)


def test_counter_marker() -> None:
    html = '<p><span class="ts-counter" id="fw:x" data-counter="fw" data-key="x">FW-01</span></p>'
    assert first_para_inlines(html) == (ir.CounterItem(key="x", prefix="fw"),)


def test_emoji_image_is_an_emoji_span() -> None:
    inlines = first_para_inlines('<p><img class="twemoji" alt="😄" src="x.svg"/></p>')
    assert inlines == (ir.SpanNode(attrs=ir.Attrs(kv=(("emoji", "😄"),)), content=(ir.Str("😄"),)),)


def test_tabbed_set() -> None:
    html = (
        '<div class="tabbed-set"><div class="tabbed-labels"><label>A</label><label>B</label></div>'
        '<div class="tabbed-content"><div class="tabbed-block"><p>one</p></div>'
        '<div class="tabbed-block"><p>two</p></div></div></div>'
    )
    block = only_block(html)
    assert block == ir.Div(
        name="tabs",
        content=(
            ir.Div(
                name="tab",
                attrs=ir.Attrs(kv=(("title", "A"),)),
                content=(ir.Para(content=(ir.Str("one"),)),),
            ),
            ir.Div(
                name="tab",
                attrs=ir.Attrs(kv=(("title", "B"),)),
                content=(ir.Para(content=(ir.Str("two"),)),),
            ),
        ),
    )


def test_generic_div_keeps_its_classes() -> None:
    block = only_block('<div class="grid cards"><p>x</p></div>')
    assert block == ir.Div(
        name="div",
        attrs=ir.Attrs(classes=("grid", "cards")),
        content=(ir.Para(content=(ir.Str("x"),)),),
    )


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def test_plain_table_to_model() -> None:
    html = (
        "<table><thead><tr><th>Name</th>"
        '<th style="text-align: right">Qty</th></tr></thead>'
        "<tbody><tr><td>Apple</td><td>3</td></tr></tbody></table>"
    )
    block = only_block(html)
    assert isinstance(block, ir.Table)
    assert block.model.columns == (
        ir.LeafColumn(name="Name"),
        ir.LeafColumn(align=ir.Align.RIGHT, name="Qty"),
    )
    assert block.model.rows == (
        ir.DataRow(cells=(ir.Cell(content=(ir.Str("Apple"),)), ir.Cell(content=(ir.Str("3"),)))),
    )


def test_plain_table_cells_carry_rich_inline() -> None:
    html = (
        "<table><thead><tr><th>Name</th><th>Desc</th></tr></thead>"
        "<tbody><tr><td><strong>Bold</strong></td>"
        "<td><code>mono</code></td></tr></tbody></table>"
    )
    block = only_block(html)
    assert isinstance(block, ir.Table)
    (row,) = block.model.rows
    assert isinstance(row, ir.DataRow)
    assert row.cells[0].content == (ir.Strong(content=(ir.Str("Bold"),)),)
    assert row.cells[1].content == (ir.Code(text="mono"),)


def test_plain_table_separator_rows() -> None:
    html = (
        "<table><thead><tr><th>A</th><th>B</th></tr></thead><tbody>"
        "<tr><td>1</td><td>2</td></tr>"
        '<tr data-ts-role="separator"><td colspan="2"></td></tr>'
        "<tr><td>3</td><td>4</td></tr></tbody></table>"
    )
    block = only_block(html)
    assert isinstance(block, ir.Table)
    assert [type(row).__name__ for row in block.model.rows] == ["DataRow", "Separator", "DataRow"]


def test_table_with_caption_and_label() -> None:
    html = (
        '<table id="t1"><caption>My Table</caption>'
        "<thead><tr><th>A</th><th>B</th></tr></thead>"
        "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
    )
    doc = read(html)
    table, caption = doc.blocks
    assert isinstance(table, ir.Table)
    assert table.attrs.id is None
    assert caption == ir.Caption(
        kind=ir.CaptionKind.TABLE, attrs=ir.Attrs(id="t1"), content=(ir.Str("My Table"),)
    )


def test_table_without_caption_keeps_its_id() -> None:
    html = (
        '<table id="t1"><thead><tr><th>A</th><th>B</th></tr></thead>'
        "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
    )
    block = only_block(html)
    assert isinstance(block, ir.Table)
    assert block.attrs.id == "t1"


def test_single_column_table_falls_back_to_div() -> None:
    emitter = _CollectingEmitter()
    doc = HtmlReader(diagnostics=emitter).read(
        "<table><tbody><tr><td>solo</td></tr></tbody></table>"
    )
    block = doc.blocks[0]
    assert isinstance(block, ir.Div)
    assert kv(block.attrs) == {"role": "table-fallback"}
    assert [record.code for record in emitter.records] == ["reader-unsupported"]


# ---------------------------------------------------------------------------
# Rich (yaml / data-ts) tables: the model is rebuilt with its spans
# ---------------------------------------------------------------------------

# The ``data-ts-table`` markup a rich table reaches the reader as. The producer
# was the ``yaml table`` Markdown extension, deleted in phase 5; the reader's
# reconstruction is still what a captured page needs, so the shapes are frozen
# here rather than generated.
SETTINGS = '<table data-ts-table="1" data-ts-env="tabularx" data-ts-colspec="l&gt;{\\raggedleft\\arraybackslash}p{\\dimexpr 3cm-2\\tabcolsep\\relax}&gt;{\\raggedright\\arraybackslash}X" data-ts-width="0.8\\linewidth" data-ts-placement="htbp"><thead><tr data-ts-role="header"><th scope="col">Item</th><th scope="col">W</th><th scope="col">Note</th></tr></thead><tbody><tr data-ts-role="body"><th scope="row">A</th><td>1</td><td>ok</td></tr></tbody></table>'

GROUPS = '<table data-ts-table="1" data-ts-env="tabular" data-ts-colspec="llll"><thead><tr data-ts-role="header"><th scope="col" rowspan="2">Item</th><th scope="col" colspan="2">Specs</th><th scope="col" rowspan="2">Note</th></tr><tr data-ts-role="header"><th scope="col">W</th><th scope="col">H</th></tr></thead><tbody><tr data-ts-role="body"><th scope="row">A</th><td>1</td><td>2</td><td>ok</td></tr><tr data-ts-role="separator" data-ts-rule="double" data-ts-sep-label="mid"><td colspan="4">mid</td></tr><tr data-ts-role="body"><th scope="row">B</th><td colspan="2">span</td><td>note</td></tr></tbody></table>'

MULTIROW = '<table data-ts-table="1" data-ts-env="tabular" data-ts-colspec="lll"><thead><tr data-ts-role="header"><th scope="col">k</th><th scope="col">a</th><th scope="col">b</th></tr></thead><tbody><tr data-ts-role="body"><th scope="row">r1</th><td rowspan="2">tall</td><td>x</td></tr><tr data-ts-role="body"><th scope="row">r2</th><td>y</td></tr><tr data-ts-role="body"><th scope="row">r3</th><td>p</td><td>q</td></tr></tbody></table>'

RICH_INLINE = '<table data-ts-table="1" data-ts-env="tabular" data-ts-colspec="lll"><thead><tr data-ts-role="header"><th scope="col">k</th><th scope="col">a</th><th scope="col">b</th></tr></thead><tbody><tr data-ts-role="body"><th scope="row">r</th><td><strong>bold</strong></td><td><code>code</code></td></tr></tbody></table>'

CAPTIONED = '<table data-ts-table="1" data-ts-env="tabular" data-ts-colspec="ll" id="tbl:x"><caption>Cap</caption><thead><tr data-ts-role="header"><th scope="col">k</th><th scope="col">a</th></tr></thead><tbody><tr data-ts-role="body"><th scope="row">r</th><td>1</td></tr></tbody></table>'


def _rich_table(html: str) -> ir.Table:
    """Lower a ``data-ts-table`` ``<table>`` and return the rebuilt model."""
    block = read(html).blocks[0]
    assert isinstance(block, ir.Table)
    return block


def test_rich_table_carries_settings() -> None:
    block = _rich_table(SETTINGS)
    assert block.model.settings == ir.TableSettings(placement="htbp", width="80%")


def test_rich_table_rebuilds_groups_spans_and_separators() -> None:
    block = _rich_table(GROUPS)
    model = block.model
    # Column group recovered from the two-level header.
    group = model.columns[1]
    assert isinstance(group, ir.ColumnGroup)
    assert [leaf.name for leaf in group.columns] == ["W", "H"]
    # Separator label + double rule recovered.
    assert model.rows[1] == ir.Separator(double_rule=True, label="mid")
    # Multicolumn span recovered: the origin cell then an absorbed slot.
    span_row = model.rows[2]
    assert isinstance(span_row, ir.DataRow)
    assert span_row.cells[1] == ir.Cell(cols=2, content=(ir.Str("span"),))
    assert span_row.cells[2] == ir.Cell(absorbed=True)
    assert span_row.cells[3] == ir.Cell(content=(ir.Str("note"),))


def test_rich_table_multirow_matches_the_parser_matrix() -> None:
    block = _rich_table(MULTIROW)
    rows = block.model.rows
    assert rows[0] == ir.DataRow(
        cells=(
            ir.Cell(content=(ir.Str("r1"),)),
            ir.Cell(content=(ir.Str("tall"),), rows=2),
            ir.Cell(content=(ir.Str("x"),)),
        )
    )
    assert rows[1] == ir.DataRow(
        cells=(
            ir.Cell(content=(ir.Str("r2"),)),
            ir.Cell(absorbed=True),
            ir.Cell(content=(ir.Str("y"),)),
        )
    )


def test_rich_table_cells_carry_rich_inline() -> None:
    block = _rich_table(RICH_INLINE)
    (row,) = block.model.rows
    assert isinstance(row, ir.DataRow)
    assert row.cells[1].content == (ir.Strong(content=(ir.Str("bold"),)),)
    assert row.cells[2].content == (ir.Code(text="code"),)


def test_rich_table_caption_and_label() -> None:
    table, caption = read(CAPTIONED).blocks
    assert isinstance(table, ir.Table)
    assert caption == ir.Caption(
        kind=ir.CaptionKind.TABLE, attrs=ir.Attrs(id="tbl:x"), content=(ir.Str("Cap"),)
    )


# ---------------------------------------------------------------------------
# Fallback / robustness — nothing is dropped silently
# ---------------------------------------------------------------------------


class _CollectingEmitter:
    debug_enabled = False

    def __init__(self) -> None:
        self.records: list[Diagnostic] = []

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        self.records.append(diagnostic)

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        pass

    def error(self, message: str, exc: BaseException | None = None) -> None:
        pass

    def event(self, name: str, payload: object) -> None:
        pass


def test_unknown_block_tag_becomes_div_with_diagnostic() -> None:
    emitter = _CollectingEmitter()
    reader = HtmlReader(diagnostics=emitter)
    doc = reader.read("<custom-block>hi</custom-block>", file=2)
    block = doc.blocks[0]
    assert block == ir.Div(
        name="div",
        attrs=ir.Attrs(kv=(("html-tag", "custom-block"),)),
        content=(ir.Para(content=(ir.Str("hi"),)),),
    )
    (record,) = emitter.records
    assert record.code == "reader-unsupported"
    assert record.span.file == 2
    assert "no block lowering" in record.message
    assert reader.diagnostics == [record]


def test_unknown_inline_tag_becomes_span_with_diagnostic() -> None:
    emitter = _CollectingEmitter()
    doc = HtmlReader(diagnostics=emitter).read("<p>a <weird>x</weird> b</p>")
    para = doc.blocks[0]
    assert isinstance(para, ir.Para)
    spans = [n for n in para.content if isinstance(n, ir.SpanNode)]
    assert spans and kv(spans[0].attrs) == {"html-tag": "weird"}
    assert any("no inline lowering" in record.message for record in emitter.records)


def test_latex_ignore_div_is_dropped_on_purpose() -> None:
    assert read('<div class="latex-ignore"><p>web only</p></div>').blocks == ()


# ---------------------------------------------------------------------------
# Registry extensibility
# ---------------------------------------------------------------------------


def test_reads_decorator_and_custom_registry() -> None:
    registry = ReaderRegistry()

    @reads("widget", level=ReadLevel.BLOCK, name="widget")
    def read_widget(tag, ctx):  # type: ignore[no-untyped-def]
        return ir.Para(content=(ir.Str("WIDGET"),))

    registry.register(read_widget.__reader_rule__.bind(read_widget))  # type: ignore[attr-defined]
    # Merge with defaults so generic text still lowers.
    from texsmith.readers.html import blocks as _b, extensions as _e, inline as _i

    registry.collect_from(_i)
    registry.collect_from(_b)
    registry.collect_from(_e)

    doc = HtmlReader(registry=registry).read("<widget/>")
    assert doc.blocks[0] == ir.Para(content=(ir.Str("WIDGET"),))


# ---------------------------------------------------------------------------
# Integration — real Markdown through the production adapter, no silent loss
# ---------------------------------------------------------------------------


#: A page in the shape MkDocs Material renders: every major construct, as the
#: ``press.reader: html`` fallback and a ``.html`` input actually see it.
MATERIAL_PAGE = """\
<h1 id="title">Title</h1>
<p>A paragraph with <strong>bold</strong>, <em>italic</em>, <code>code</code> \
and a <a href="https://x.io">link</a>.</p>
<ul>
<li>one</li>
<li>two</li>
</ul>
<ol>
<li>first</li>
<li>second</li>
</ol>
<blockquote>
<p>a quote</p>
</blockquote>
<div class="admonition note">
<p class="admonition-title">Note</p>
<p>inside the note</p>
</div>
<table>
<thead>
<tr><th>A</th><th>B</th></tr>
</thead>
<tbody>
<tr><td>1</td><td>2</td></tr>
</tbody>
</table>
<div class="highlight"><pre><code class="language-python">print('hi')
</code></pre></div>
<dl>
<dt>Term</dt>
<dd>Definition</dd>
</dl>
"""


def test_a_rendered_page_reaches_the_ir_without_silent_loss() -> None:
    from texsmith.ir import codec

    emitter = _CollectingEmitter()
    doc = HtmlReader(diagnostics=emitter).read(MATERIAL_PAGE)

    kinds = {type(n).__name__ for n in walk(doc)}
    # The major constructs all surface as their typed nodes.
    for expected in {
        "Header",
        "Para",
        "Strong",
        "Emph",
        "Code",
        "Link",
        "BulletList",
        "OrderedList",
        "BlockQuote",
        "Admonition",
        "Table",
        "CodeBlock",
        "DefinitionList",
    }:
        assert expected in kinds, f"missing {expected}; got {sorted(kinds)}"

    # No construct was dropped to a generic fallback, and the document
    # round-trips through the codec like a ``tmark.parse`` result.
    assert emitter.records == []
    assert codec.decode_document(codec.encode_document(doc)) == doc
