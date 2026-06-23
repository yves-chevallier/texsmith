"""Unit tests for the HTML→IR reader (Phase 2).

One case per node type / handler: a hand-written HTML fixture is lowered and the
resulting IR is asserted structurally. A final integration test runs real
Markdown through the production adapter and checks that no construct is dropped
silently.
"""

from __future__ import annotations

from texsmith.ir import nodes as ir
from texsmith.readers.html import HtmlReader, ReaderRegistry, ReadLevel, reads


def read(html: str) -> ir.Document:
    return HtmlReader().read(html)


def only_block(html: str) -> ir.Block:
    doc = read(html)
    assert len(doc.content) == 1, doc.content
    return doc.content[0]


def first_para_inlines(html: str) -> tuple[ir.Inline, ...]:
    block = only_block(html)
    assert isinstance(block, ir.Para)
    return block.content


# ---------------------------------------------------------------------------
# Text / whitespace
# ---------------------------------------------------------------------------


def test_text_splits_into_str_and_space() -> None:
    inlines = first_para_inlines("<p>hello world</p>")
    assert inlines == (ir.Str("hello"), ir.Space(), ir.Str("world"))


def test_leading_trailing_space_stripped_in_paragraph() -> None:
    inlines = first_para_inlines("<p>  spaced  </p>")
    assert inlines == (ir.Str("spaced"),)


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


# ---------------------------------------------------------------------------
# Code
# ---------------------------------------------------------------------------


def test_inline_code() -> None:
    inlines = first_para_inlines('<p><code class="language-python">x=1</code></p>')
    assert inlines == (ir.Code(text="x=1", lang="python"),)


def test_inline_code_plain() -> None:
    inlines = first_para_inlines("<p><code>raw</code></p>")
    assert inlines == (ir.Code(text="raw", lang=""),)


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
    assert block.filename == "main.py"
    assert block.lineno is True


def test_mermaid_pre_is_code_block() -> None:
    block = only_block('<pre class="mermaid"><code>graph TD\nA-->B</code></pre>')
    assert isinstance(block, ir.CodeBlock)
    assert block.lang == "mermaid"
    assert "graph TD" in block.text


# ---------------------------------------------------------------------------
# Headings, rules, paragraphs
# ---------------------------------------------------------------------------


def test_heading_with_identifier_and_anchor_dropped() -> None:
    block = only_block('<h2 id="sec">Title<a class="headerlink" href="#sec">¶</a></h2>')
    assert block == ir.Header(level=2, content=(ir.Str("Title"),), identifier="sec")


def test_horizontal_rule() -> None:
    assert only_block("<hr/>") == ir.HorizontalRule()


def test_latex_raw_paragraph() -> None:
    block = only_block('<p class="latex-raw">\\foo{bar}</p>')
    assert block == ir.RawBlock(format="latex", text="\\foo{bar}")


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


def test_bullet_list_tight_items_are_plain() -> None:
    block = only_block("<ul><li>a</li><li>b</li></ul>")
    assert block == ir.BulletList(
        items=(
            (ir.Plain(content=(ir.Str("a"),)),),
            (ir.Plain(content=(ir.Str("b"),)),),
        )
    )


def test_ordered_list_start_and_style() -> None:
    block = only_block('<ol start="3" type="a"><li>x</li></ol>')
    assert isinstance(block, ir.OrderedList)
    assert block.start == 3
    assert block.style is ir.ListStyle.LOWER_ALPHA


def test_task_list_marker() -> None:
    block = only_block('<ul><li><input type="checkbox" checked/> done</li></ul>')
    assert isinstance(block, ir.BulletList)
    first_item = block.items[0]
    marker = first_item[0]
    assert isinstance(marker, ir.Div)
    assert ("role", "task-marker") in marker.attrs
    assert ("checked", "true") in marker.attrs


def test_definition_list() -> None:
    block = only_block("<dl><dt>Term</dt><dd>Def</dd></dl>")
    assert isinstance(block, ir.DefinitionList)
    item = block.items[0]
    assert item.term == (ir.Str("Term"),)
    assert item.definitions[0] == (ir.Para(content=(ir.Str("Def"),)),)


# ---------------------------------------------------------------------------
# Blockquote
# ---------------------------------------------------------------------------


def test_blockquote() -> None:
    block = only_block("<blockquote><p>quoted</p></blockquote>")
    assert block == ir.BlockQuote(content=(ir.Para(content=(ir.Str("quoted"),)),))


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
    assert inlines == (ir.Link(content=(ir.Str("go"),), target="https://x.io", title="t"),)


def test_anchor_link() -> None:
    inlines = first_para_inlines('<p><a href="#sec">see</a></p>')
    assert inlines == (ir.Link(content=(ir.Str("see"),), target="#sec"),)


def test_autoref() -> None:
    inlines = first_para_inlines("<p><autoref identifier='fig:1'>Fig</autoref></p>")
    assert inlines == (ir.Link(content=(ir.Str("Fig"),), target="#fig:1"),)


# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------


def test_inline_math_arithmatex() -> None:
    inlines = first_para_inlines('<p><span class="arithmatex">\\(a+b\\)</span></p>')
    assert inlines == (ir.Math(text="a+b", display=False),)


def test_block_math() -> None:
    block = only_block('<div class="arithmatex">\\[E=mc^2\\]</div>')
    assert block == ir.Plain(content=(ir.Math(text="E=mc^2", display=True),))


def test_math_script_display() -> None:
    block = only_block('<script type="math/tex; mode=display">x^2</script>')
    # script is ANY-level; at block level it becomes a Para-wrapped inline.
    assert any(isinstance(n, ir.Math) and n.display for n in _walk_inlines(block))


def _walk_inlines(node: ir.Node) -> list[ir.Inline]:
    from texsmith.ir import walk

    return [n for n in walk(node) if isinstance(n, ir.Inline)]


# ---------------------------------------------------------------------------
# Images / figures
# ---------------------------------------------------------------------------


def test_inline_image() -> None:
    inlines = first_para_inlines('<p><img src="a.png" alt="alt" width="50"/></p>')
    assert inlines == (ir.Image(src="a.png", alt=(ir.Str("alt"),), title="", width="50"),)


def test_figure_with_caption() -> None:
    block = only_block('<figure id="f1"><img src="a.png"/><figcaption>Cap</figcaption></figure>')
    assert isinstance(block, ir.Figure)
    assert block.identifier == "f1"
    assert block.caption == (ir.Str("Cap"),)


# ---------------------------------------------------------------------------
# Extension constructs
# ---------------------------------------------------------------------------


def test_admonition_div() -> None:
    html = '<div class="admonition note"><p class="admonition-title">Note</p><p>body</p></div>'
    block = only_block(html)
    assert isinstance(block, ir.Admonition)
    assert block.kind == "note"
    assert block.title == (ir.Str("Note"),)
    assert block.content == (ir.Para(content=(ir.Str("body"),)),)
    assert block.collapsible is False


def test_details_collapsible_admonition() -> None:
    block = only_block("<details class='tip'><summary>More</summary><p>x</p></details>")
    assert isinstance(block, ir.Admonition)
    assert block.kind == "tip"
    assert block.collapsible is True
    assert block.title == (ir.Str("More"),)


def test_marginnote_side() -> None:
    # A margin note is inline-natured: at the top level it is wrapped in a Para.
    inlines = first_para_inlines('<p>x <ts-marginnote data-side="l">hi</ts-marginnote></p>')
    note = inlines[-1]
    assert isinstance(note, ir.MarginNote)
    assert note.side is ir.MarginSide.LEFT
    assert note.content == (ir.Plain(content=(ir.Str("hi"),)),)


def test_progressbar() -> None:
    html = (
        '<div class="progress thin" data-progress-percent="40">'
        '<div class="progress-bar"><p class="progress-label">L</p></div></div>'
    )
    block = only_block(html)
    assert isinstance(block, ir.ProgressBar)
    assert abs(block.fraction - 0.4) < 1e-9
    assert block.thin is True
    assert block.label == (ir.Str("L"),)


def test_index_entry() -> None:
    html = (
        '<p><span class="ts-hashtag" data-tag="Animal" data-tag1="Cat" data-style="b"></span></p>'
    )
    inlines = first_para_inlines(html)
    entry = inlines[0]
    assert isinstance(entry, ir.IndexEntry)
    assert entry.path == ("Animal", "Cat")
    assert entry.style == "b"


def test_texlogo() -> None:
    inlines = first_para_inlines(
        '<p><span class="tex-logo tex-latex" data-tex-logo="latex">LaTeX</span></p>'
    )
    assert inlines == (ir.TexLogo(name="latex"),)


def test_keystroke() -> None:
    html = '<p><span class="keys"><kbd class="key-control">Ctrl</kbd><kbd class="key-s">S</kbd></span></p>'
    inlines = first_para_inlines(html)
    assert inlines == (ir.Keystroke(keys=("control", "s")),)


def test_abbreviation_span_role() -> None:
    inlines = first_para_inlines('<p><abbr title="HyperText">HTML</abbr></p>')
    span = inlines[0]
    assert isinstance(span, ir.Span)
    assert ("role", "abbr") in span.attrs
    assert ("title", "HyperText") in span.attrs


def test_critic_deletion_role() -> None:
    inlines = first_para_inlines('<p><del class="critic">gone</del></p>')
    span = inlines[0]
    assert isinstance(span, ir.Span)
    assert ("role", "critic-deletion") in span.attrs


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def test_plain_table_to_schema_model() -> None:
    html = (
        "<table><thead><tr><th>Name</th>"
        '<th style="text-align: right">Qty</th></tr></thead>'
        "<tbody><tr><td>Apple</td><td>3</td></tr></tbody></table>"
    )
    block = only_block(html)
    assert isinstance(block, ir.Table)
    model = block.model
    assert len(model.columns) == 2
    # Right alignment recovered from the inline style.
    assert model.columns[1].align == "r"
    assert model.rows[0].label == "Apple"
    assert model.rows[0].cells == ["3"]


def test_plain_table_cells_carry_rich_inline() -> None:
    # Cell content (bold, inline code) must survive as inline IR, not flattened
    # to scalar text — the scalar ``model`` cannot hold it.
    html = (
        "<table><thead><tr><th>Name</th><th>Desc</th></tr></thead>"
        "<tbody><tr><td><strong>Bold</strong></td>"
        "<td><code>mono</code></td></tr></tbody></table>"
    )
    block = only_block(html)
    assert isinstance(block, ir.Table)
    # HTML document order: header cells, then the body row's cells.
    assert block.cells == (
        (ir.Str("Name"),),
        (ir.Str("Desc"),),
        (ir.Strong(content=(ir.Str("Bold"),)),),
        (ir.Code(text="mono"),),
    )


def test_plain_table_cells_match_writer_iteration_order() -> None:
    # The flat ``cells`` tuple must line up with the writer's plain-path order:
    # leaf columns, then per data row ``[label, *cells]`` (separators skipped).
    from texsmith.extensions.tables import schema as tbl

    html = (
        "<table><thead><tr><th>A</th><th>B</th></tr></thead><tbody>"
        "<tr><td>1</td><td>2</td></tr>"
        '<tr data-ts-role="separator"><td colspan="2"></td></tr>'
        "<tr><td>3</td><td>4</td></tr></tbody></table>"
    )
    block = only_block(html)
    assert isinstance(block, ir.Table)
    model = block.model
    expected = len([leaf for c in model.columns for leaf in tbl.column_leaves(c)])
    for row in model.rows:
        if isinstance(row, tbl.Separator):
            continue
        expected += 1 + len(row.cells)
    assert len(block.cells) == expected


def test_table_with_caption_and_label() -> None:
    html = (
        '<table id="t1"><caption>My Table</caption>'
        "<thead><tr><th>A</th><th>B</th></tr></thead>"
        "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
    )
    block = only_block(html)
    assert isinstance(block, ir.Table)
    assert block.label == "t1"
    assert block.caption == (ir.Str("My"), ir.Space(), ir.Str("Table"))


def test_single_column_table_falls_back_to_div() -> None:
    html = "<table><tbody><tr><td>solo</td></tr></tbody></table>"
    block = only_block(html)
    assert isinstance(block, ir.Div)
    assert ("role", "table-fallback") in block.attrs


def test_plain_gfm_table_has_empty_layout_fields() -> None:
    # A plain GFM table (no ``data-ts-table``) carries no layout presentation;
    # the writer takes the plain ``table.tex`` path.
    html = (
        "<table><thead><tr><th>A</th><th>B</th></tr></thead>"
        "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
    )
    block = only_block(html)
    assert isinstance(block, ir.Table)
    assert block.env == ""
    assert block.colspec == ""
    assert block.width == ""
    assert block.placement == ""


# ---------------------------------------------------------------------------
# Rich (yaml / data-ts) tables: presentation carried + rich model rebuilt
# ---------------------------------------------------------------------------


def _rich_table(payload: dict, **kw) -> ir.Table:
    """Render a yaml-table payload to its ``data-ts`` HTML, then lower it."""
    from texsmith.extensions.tables.html import render_table_html
    from texsmith.extensions.tables.schema import parse_table

    html = render_table_html(parse_table(payload), **kw)
    block = only_block(html)
    assert isinstance(block, ir.Table)
    return block


def test_rich_table_carries_layout_presentation_verbatim() -> None:
    block = _rich_table(
        {
            "table": {"width": "80%", "placement": "htbp"},
            "columns": [
                {"name": "Item"},
                {"name": "W", "width": "3cm", "align": "r"},
                {"name": "Note", "width": "X"},
            ],
            "rows": [["A", 1, "ok"]],
        }
    )
    # The precomputed layout directive is lifted straight from the data-ts-*
    # attributes (per-column widths / preamble wrappers are not recoverable
    # from cell text, so they are carried, not re-derived).
    assert block.env == "tabularx"
    assert block.width == "0.8\\linewidth"
    assert block.placement == "htbp"
    assert "p{3cm}" in block.colspec
    assert "X" in block.colspec


def test_rich_table_layout_fields_match_compute_layout() -> None:
    from texsmith.extensions.tables.layout import compute_layout

    payload = {
        "columns": [
            {"name": "Item"},
            {"name": "Specs", "columns": [{"name": "W"}, {"name": "H"}]},
            {"name": "Note"},
        ],
        "rows": [["A", [1, 2], "ok"]],
    }
    block = _rich_table(payload)
    lay = compute_layout(block.model)
    # The reconstructed model regenerates the identical layout the reader
    # carried, so a writer may trust either source.
    assert lay.env == block.env
    assert lay.colspec == block.colspec
    assert (lay.total_width_spec or "") == block.width
    assert (lay.placement or "") == block.placement


def test_rich_table_rebuilds_groups_spans_and_separators() -> None:
    from texsmith.extensions.tables import schema as tbl

    block = _rich_table(
        {
            "columns": [
                {"name": "Item"},
                {"name": "Specs", "columns": [{"name": "W"}, {"name": "H"}]},
                {"name": "Note"},
            ],
            "rows": [
                ["A", [1, 2], "ok"],
                {"separator": {"label": "mid", "double-rule": True}},
                ["B", {"value": "span", "cols": 2}, "note"],
            ],
        }
    )
    model = block.model
    # Column group recovered from the two-level header.
    assert isinstance(model.columns[1], tbl.ColumnGroup)
    assert [leaf.name for leaf in model.columns[1].columns] == ["W", "H"]
    # Separator label + double rule recovered.
    sep = model.rows[1]
    assert isinstance(sep, tbl.Separator)
    assert sep.label == "mid"
    assert sep.double_rule is True
    # Multicolumn span recovered as a RichCell. Here the span fills the
    # two-leaf ``Specs`` group, so it lands inside that column's leaf list.
    span_row = model.rows[2]
    assert isinstance(span_row, tbl.DataRow)
    group_cell = span_row.cells[0]
    assert isinstance(group_cell, list)
    assert isinstance(group_cell[0], tbl.RichCell)
    assert group_cell[0].cols == 2


def test_rich_table_cross_column_span_recovered() -> None:
    from texsmith.extensions.tables import schema as tbl

    # A multicolumn cell spanning two *separate* single-leaf data columns is
    # placed as one positional RichCell at the top level (``_place_rich``).
    block = _rich_table(
        {
            "columns": [{"name": "k"}, {"name": "a"}, {"name": "b"}],
            "rows": [
                ["r1", {"value": "wide", "cols": 2}],
                ["r2", "p", "q"],
            ],
        }
    )
    wide_row = block.model.rows[0]
    assert isinstance(wide_row, tbl.DataRow)
    assert isinstance(wide_row.cells[0], tbl.RichCell)
    assert wide_row.cells[0].cols == 2


def test_rich_table_cells_align_with_regenerated_html_order() -> None:
    # The writer's yaml path walks the <th>/<td> of render_table_html(node.model)
    # in document order; ``cells`` must line up one-to-one (caption + separator
    # rows excluded).
    from bs4 import BeautifulSoup

    from texsmith.extensions.tables.html import render_table_html

    block = _rich_table(
        {
            "columns": [
                {"name": "Item"},
                {"name": "Specs", "columns": [{"name": "W"}, {"name": "H"}]},
                {"name": "Note"},
            ],
            "rows": [
                ["A", [1, 2], "ok"],
                {"separator": {"label": "mid"}},
                ["B", {"value": "span", "cols": 2}, "note"],
            ],
        },
        caption="Cap",
        label="x",
    )
    regen = render_table_html(block.model, caption="Cap", label="x")
    soup = BeautifulSoup(regen, "html.parser")
    html_cells = [
        c
        for c in soup.find("table").find_all(["th", "td"])
        if c.find_parent("caption") is None
        and c.find_parent("tr").get("data-ts-role") != "separator"
    ]
    assert len(html_cells) == len(block.cells)


def test_rich_table_cells_carry_rich_inline() -> None:
    # Inline markup inside a yaml-table cell survives as inline IR.
    block = _rich_table(
        {
            "columns": [{"name": "k"}, {"name": "a"}, {"name": "b"}],
            "rows": [["r", "**bold**", "`code`"]],
        }
    )
    flat = [node for run in block.cells for node in run]
    assert any(isinstance(n, ir.Strong) for n in flat)
    assert any(isinstance(n, ir.Code) for n in flat)


def test_rich_table_roundtrips_to_identical_inner_html() -> None:
    # The reconstructed model must re-render to the same thead/tbody/tfoot the
    # extension produced, because the writer replays the legacy row assembler
    # over ``render_table_html(node.model)``.
    from bs4 import BeautifulSoup

    from texsmith.extensions.tables.html import render_table_html
    from texsmith.extensions.tables.schema import parse_table

    payload = {
        "columns": [{"name": "k"}, {"name": "a"}, {"name": "b"}],
        "rows": [
            ["r1", {"value": "tall", "rows": 2}, "x"],
            ["r2", None, "y"],
            ["r3", "p", "q"],
        ],
    }
    original_html = render_table_html(parse_table(payload))
    block = only_block(original_html)
    assert isinstance(block, ir.Table)
    rebuilt_html = render_table_html(block.model)
    orig = BeautifulSoup(original_html, "html.parser")
    rebuilt = BeautifulSoup(rebuilt_html, "html.parser")
    for section in ("thead", "tbody", "tfoot"):
        assert str(orig.find(section)) == str(rebuilt.find(section))


# ---------------------------------------------------------------------------
# Fallback / robustness — nothing is dropped silently
# ---------------------------------------------------------------------------


class _CollectingEmitter:
    debug_enabled = False

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        self.warnings.append(message)

    def error(self, message: str, exc: BaseException | None = None) -> None:
        pass

    def event(self, name: str, payload: object) -> None:
        pass


def test_unknown_block_tag_becomes_div_with_warning() -> None:
    emitter = _CollectingEmitter()
    doc = HtmlReader(diagnostics=emitter).read("<custom-block>hi</custom-block>")
    block = doc.content[0]
    assert isinstance(block, ir.Div)
    assert ("html-tag", "custom-block") in block.attrs
    assert any("no block lowering" in w for w in emitter.warnings)


def test_unknown_inline_tag_becomes_span_with_warning() -> None:
    emitter = _CollectingEmitter()
    doc = HtmlReader(diagnostics=emitter).read("<p>a <weird>x</weird> b</p>")
    para = doc.content[0]
    assert isinstance(para, ir.Para)
    spans = [n for n in para.content if isinstance(n, ir.Span)]
    assert spans and ("html-tag", "weird") in spans[0].attrs
    assert any("no inline lowering" in w for w in emitter.warnings)


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
    assert doc.content[0] == ir.Para(content=(ir.Str("WIDGET"),))


# ---------------------------------------------------------------------------
# Integration — real Markdown through the production adapter, no silent loss
# ---------------------------------------------------------------------------


def test_markdown_to_html_to_ir_no_silent_loss() -> None:
    from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown

    source = "\n".join(
        [
            "# Title",
            "",
            "A paragraph with **bold**, *italic*, `code` and a [link](https://x.io).",
            "",
            "- one",
            "- two",
            "",
            "1. first",
            "2. second",
            "",
            "> a quote",
            "",
            "!!! note",
            "    inside the note",
            "",
            "| A | B |",
            "|---|---|",
            "| 1 | 2 |",
            "",
            "```python",
            "print('hi')",
            "```",
            "",
            "Term",
            ": Definition",
        ]
    )
    document = render_markdown(source, extensions=DEFAULT_MARKDOWN_EXTENSIONS)
    emitter = _CollectingEmitter()
    doc = HtmlReader(diagnostics=emitter).read(document.html)

    from texsmith.ir import walk

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

    # No construct was dropped to a generic fallback.
    assert not any("no block lowering" in w for w in emitter.warnings), emitter.warnings
    assert not any("no inline lowering" in w for w in emitter.warnings), emitter.warnings
