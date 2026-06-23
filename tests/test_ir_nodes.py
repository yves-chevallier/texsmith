"""Unit tests for the IR node hierarchy: construction, equality, immutability."""

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

for candidate in (PROJECT_ROOT, SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from texsmith import ir  # noqa: E402
from texsmith.extensions.tables.schema import parse_table  # noqa: E402


def text(value: str) -> tuple[ir.Str, ...]:
    return (ir.Str(value),)


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------


def test_inline_and_block_are_nodes() -> None:
    assert isinstance(ir.Str("x"), ir.Inline)
    assert isinstance(ir.Para(()), ir.Block)
    assert isinstance(ir.Str("x"), ir.Node)
    assert isinstance(ir.Para(()), ir.Node)
    # Inline is not Block and vice-versa.
    assert not isinstance(ir.Str("x"), ir.Block)
    assert not isinstance(ir.Para(()), ir.Inline)


def test_document_is_a_block() -> None:
    doc = ir.Document((ir.Para(text("hi")),))
    assert isinstance(doc, ir.Block)
    assert doc.content[0].content[0].text == "hi"


def test_defaults_are_applied() -> None:
    assert ir.Code("x").lang == ""
    assert ir.Math("x").display is False
    assert ir.Link((), "u").title == ""
    assert ir.Cite(("k",)).mode is ir.CitationMode.NORMAL
    assert ir.OrderedList(()).start == 1
    assert ir.OrderedList(()).style is ir.ListStyle.DECIMAL
    assert ir.MarginNote(()).side is ir.MarginSide.RIGHT
    assert ir.Header(1, ()).numbered is True


def test_nested_inline_construction() -> None:
    node = ir.Emph((ir.Str("a"), ir.Space(), ir.Strong(text("b"))))
    assert node.content[2].content[0].text == "b"


# --------------------------------------------------------------------------
# Structural equality & hashing
# --------------------------------------------------------------------------


def test_structural_equality() -> None:
    a = ir.Para((ir.Str("hi"), ir.Space(), ir.Str("there")))
    b = ir.Para((ir.Str("hi"), ir.Space(), ir.Str("there")))
    assert a == b
    assert a is not b


def test_inequality_on_field_difference() -> None:
    assert ir.Str("a") != ir.Str("b")
    assert ir.Header(1, text("t")) != ir.Header(2, text("t"))


def test_nodes_are_hashable() -> None:
    node = ir.Para((ir.Str("x"), ir.Space()))
    assert hash(node) == hash(ir.Para((ir.Str("x"), ir.Space())))
    # usable in a set / dict key
    assert len({node, ir.Para((ir.Str("x"), ir.Space()))}) == 1


# --------------------------------------------------------------------------
# Immutability
# --------------------------------------------------------------------------


def test_nodes_are_frozen() -> None:
    node = ir.Str("x")
    with pytest.raises(FrozenInstanceError):
        node.text = "y"  # type: ignore[misc]


def test_slots_block_unknown_attributes() -> None:
    node = ir.Space()
    with pytest.raises((AttributeError, TypeError)):
        node.surprise = 1  # type: ignore[attr-defined]


# --------------------------------------------------------------------------
# Semantic alignment enum
# --------------------------------------------------------------------------


def test_alignment_from_short() -> None:
    assert ir.Alignment.from_short("l") is ir.Alignment.LEFT
    assert ir.Alignment.from_short("c") is ir.Alignment.CENTER
    assert ir.Alignment.from_short("r") is ir.Alignment.RIGHT
    assert ir.Alignment.from_short("j") is ir.Alignment.JUSTIFY


def test_alignment_rejects_latex_letters() -> None:
    with pytest.raises(KeyError):
        ir.Alignment.from_short("X")


# --------------------------------------------------------------------------
# Table wraps the semantic tables model without loss
# --------------------------------------------------------------------------


def test_table_holds_semantic_model() -> None:
    model = parse_table(
        {
            "columns": ["", {"name": "Qty", "align": "right"}],
            "rows": [["apples", 3], ["pears", 5]],
        }
    )
    node = ir.Table(model=model, caption=text("Fruit"), label="tbl:fruit")
    # alignment in the embedded model is the semantic one-letter form, never a
    # LaTeX preamble string.
    qty = node.model.columns[1]
    assert qty.align == "r"
    assert ir.Alignment.from_short(qty.align) is ir.Alignment.RIGHT
    assert node.label == "tbl:fruit"
    assert node.caption[0].text == "Fruit"
    # Layout presentation fields default to empty (plain-GFM path).
    assert node.env == ""
    assert node.colspec == ""
    assert node.width == ""
    assert node.placement == ""
    # Rich-cell content defaults to empty (shape lives in ``model``).
    assert node.cells == ()


def test_table_cells_carry_inline_and_are_traversed() -> None:
    from texsmith.ir.visitor import walk

    model = parse_table({"columns": ["A", "B"], "rows": [["x", "y"]]})
    bold = ir.Strong(content=(ir.Str("x"),))
    node = ir.Table(
        model=model,
        cells=((ir.Str("A"),), (ir.Str("B"),), (bold,), (ir.Code(text="y"),)),
    )
    assert node.cells[2] == (bold,)
    # ``cells`` are real children: the visitor walks them (so font-fallback /
    # citation scans reach cell content too).
    assert any(n is bold for n in walk(node))


def test_table_layout_presentation_fields() -> None:
    model = parse_table(
        {
            "columns": ["", {"name": "Qty"}],
            "rows": [["apples", 3]],
        }
    )
    node = ir.Table(
        model=model,
        env="tabularx",
        colspec=r">{\raggedright\arraybackslash}Xr",
        width=r"\linewidth",
        placement="htbp",
    )
    # The rich-table escape hatch carries the precomputed layout directive
    # verbatim (the extension's own format, not a generic backend string).
    assert node.env == "tabularx"
    assert node.colspec == r">{\raggedright\arraybackslash}Xr"
    assert node.width == r"\linewidth"
    assert node.placement == "htbp"


# --------------------------------------------------------------------------
# Escape hatches & generic containers
# --------------------------------------------------------------------------


def test_raw_nodes_carry_format() -> None:
    assert ir.RawInline("latex", "\\foo").format == "latex"
    assert ir.RawBlock("typst", "#bar").format == "typst"


def test_generic_containers_carry_attrs() -> None:
    span = ir.Span(text("WWW"), (("role", "abbr"), ("title", "World Wide Web")))
    div = ir.Div((ir.Para(text("x")),), (("role", "multicolumn"), ("columns", "2")))
    assert dict(span.attrs)["title"] == "World Wide Web"
    assert dict(div.attrs)["columns"] == "2"
