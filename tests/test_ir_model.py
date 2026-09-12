"""The generated IR models against tmark's conformance fixtures and real output.

Fixtures live under ``tests/fixtures/tmark-ir`` (refreshed by
``scripts/refresh_tmark_fixtures.py``): every ``## ir`` block of the
conformance files is structural JSON (no ids, spans or absent values), and
``parsed/*.json`` is the exact ``tmark parse`` output of each canonical block.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for candidate in (PROJECT_ROOT, SRC_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from texsmith import ir  # noqa: E402
from texsmith.ir import codec, model  # noqa: E402
from texsmith.ir.codec import (  # noqa: E402
    IRDecodeError,
    decode_document,
    encode_document,
    structural,
)
from texsmith.ir.model import MISSING, NO_SPAN, Span  # noqa: E402
from texsmith.ir.walk import NodeVisitor, children, map_tree, plain_text, walk  # noqa: E402


FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "tmark-ir"
CONFORMANCE = sorted((FIXTURES / "conformance").glob("*.md"))
PARSED = sorted((FIXTURES / "parsed").glob("*.json"))


# --------------------------------------------------------------------------
# Fixture access
# --------------------------------------------------------------------------


def fenced_sections(text: str) -> dict[str, list[tuple[str, str]]]:
    """``{section: [(language, content)]}`` of a conformance file (tmark's runner)."""
    out: dict[str, list[tuple[str, str]]] = {}
    current = ""
    fence: tuple[str, list[str], int] | None = None
    for line in text.splitlines():
        if fence is not None:
            lang, content, length = fence
            stripped = line.rstrip()
            if stripped and set(stripped) == {"`"} and len(stripped) >= length:
                out.setdefault(current, []).append((lang, "".join(content)))
                fence = None
            else:
                content.append(line + "\n")
            continue
        if line.startswith("## "):
            current = line[3:].strip()
        elif line.startswith("```"):
            length = len(line) - len(line.lstrip("`"))
            fence = (line[length:].strip(), [], length)
    return out


def fixture_ir(path: Path) -> dict[str, Any]:
    return json.loads(fenced_sections(path.read_text(encoding="utf-8"))["ir"][0][1])


def strip_absent(value: Any) -> Any:
    """A fixture may spell absent values explicitly; ``structural`` never does."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            item = strip_absent(item)
            if item is None or (isinstance(item, str | list | dict) and not item):
                continue
            out[key] = item
        return out
    if isinstance(value, list):
        return [strip_absent(item) for item in value]
    return value


def reference_walk(doc: model.Document) -> list[model.Node]:
    """A literal port of ``tmark_ir::walk`` (``walk.rs``): the expected pre-order."""
    out: list[model.Node] = []

    def blocks(items: tuple[model.Block, ...]) -> None:
        for block in items:
            out.append(block)
            match block:
                case model.Para(lead=lead, content=content):
                    if lead is not None:
                        inlines(lead)
                    inlines(content)
                case model.Plain(content=content) | model.Header(content=content):
                    inlines(content)
                case model.Caption(content=content):
                    inlines(content)
                case model.BlockQuote(content=content) | model.Figure(content=content):
                    blocks(content)
                case model.Div(content=content):
                    blocks(content)
                case model.BulletList(items=items) | model.OrderedList(items=items):
                    for item in items:
                        blocks(item.content)
                case model.DefinitionList(items=items):
                    for term, definitions in items:
                        inlines(term)
                        for definition in definitions:
                            blocks(definition)
                case model.Table(model=table):
                    columns(table.columns)
                    for row in (*table.rows, *table.footer):
                        if isinstance(row, model.DataRow):
                            for cell in row.cells:
                                inlines(cell.content)
                case model.Admonition(title=title, content=content):
                    if title is not None:
                        inlines(title)
                    blocks(content)
                case _:
                    pass

    def columns(items: tuple[model.Column, ...]) -> None:
        for column in items:
            if isinstance(column, model.LeafColumn):
                inlines(column.title)
            else:
                inlines(column.title)
                columns(column.columns)

    def inlines(items: tuple[model.Inline, ...]) -> None:
        for inline in items:
            out.append(inline)
            match inline:
                case model.Note(content=content) | model.Aside(content=content):
                    blocks(content)
                case model.Image(alt=alt):
                    inlines(alt)
                case model.IndexEntry(path=path):
                    for level in path:
                        inlines(level)
                case model.Link(content=content) | model.SpanNode(content=content):
                    inlines(content)
                case (
                    model.Emph(content=content)
                    | model.Strong(content=content)
                    | model.Strikeout(content=content)
                    | model.Underline(content=content)
                    | model.Highlight(content=content)
                    | model.Subscript(content=content)
                    | model.Superscript(content=content)
                    | model.SmallCaps(content=content)
                    | model.Quoted(content=content)
                ):
                    inlines(content)
                case _:
                    pass

    blocks(doc.blocks)
    for footnote in doc.footnotes:
        blocks(footnote.content)
    return out


# --------------------------------------------------------------------------
# Conformance fixtures: decode, structural view, stability
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", CONFORMANCE, ids=[p.stem for p in CONFORMANCE])
def test_conformance_ir_decodes_to_its_structural_view(path: Path) -> None:
    data = fixture_ir(path)
    doc = decode_document(data)
    assert structural(doc) == strip_absent(data)


@pytest.mark.parametrize("path", CONFORMANCE, ids=[p.stem for p in CONFORMANCE])
def test_conformance_structural_view_decodes_back_equal(path: Path) -> None:
    doc = decode_document(fixture_ir(path))
    assert decode_document(structural(doc)) == doc


# --------------------------------------------------------------------------
# Real tmark output: exact round trip, identity, walk order
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", PARSED, ids=[p.stem for p in PARSED])
def test_parsed_output_round_trips_exactly(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert encode_document(decode_document(data)) == data


@pytest.mark.parametrize("path", PARSED, ids=[p.stem for p in PARSED])
def test_parsed_output_matches_fixture_modulo_identity(path: Path) -> None:
    parsed = decode_document(json.loads(path.read_text(encoding="utf-8")))
    fixture = decode_document(fixture_ir(FIXTURES / "conformance" / f"{path.stem}.md"))
    # Same structure with and without ids and spans. (Dataclass ``==`` also
    # ignores node ids and spans, but not the ``id_span``/``key_span`` of
    # ``Attrs``/``RefItem`` nor the sugar fields, exactly as Rust ``==``; the
    # structural view is the comparison tmark's own conformance runner makes.)
    assert structural(parsed) == structural(fixture)
    assert decode_document(structural(parsed)) == fixture
    if parsed.blocks:
        first = parsed.blocks[0]
        assert first.id != 0 or first.span != NO_SPAN
        assert fixture.blocks[0].id == 0 and fixture.blocks[0].span == NO_SPAN


@pytest.mark.parametrize("path", PARSED, ids=[p.stem for p in PARSED])
def test_walk_is_tmarks_preorder(path: Path) -> None:
    doc = decode_document(json.loads(path.read_text(encoding="utf-8")))
    expected = reference_walk(doc)
    got = list(walk(doc))
    assert [(type(n).__name__, n.id) for n in got] == [(type(n).__name__, n.id) for n in expected]
    assert all(a is b for a, b in zip(got, expected, strict=True))


def test_walk_visits_lead_and_title_first() -> None:
    lead = (model.Str("Lead"),)
    para = model.Para(lead=lead, content=(model.Str("body"),))
    assert [n.text for n in walk(para) if isinstance(n, model.Str)] == ["Lead", "body"]
    adm = model.Admonition(
        kind="note",
        title=(model.Str("Title"),),
        content=(model.Para(content=(model.Str("Body"),)),),
    )
    assert [n.text for n in walk(adm) if isinstance(n, model.Str)] == ["Title", "Body"]


# --------------------------------------------------------------------------
# Front matter: MISSING versus None
# --------------------------------------------------------------------------


def test_title_null_is_none_and_absent_is_missing() -> None:
    explicit = decode_document({"front_matter": {"keys": {"title": None}}})
    absent = decode_document({"front_matter": {"keys": {}}})
    assert explicit.front_matter.keys.title is None
    assert absent.front_matter.keys.title is MISSING
    assert explicit.front_matter.keys != absent.front_matter.keys
    assert encode_document(explicit)["front_matter"]["keys"] == {"title": None}
    assert encode_document(absent)["front_matter"]["keys"] == {}
    assert repr(MISSING) == "MISSING"


def test_front_matter_extra_and_json_blobs() -> None:
    data = {
        "front_matter": {
            "keys": {"press": {"declare": {"acronyms": {"HTML": "HyperText"}}}},
            "extra": {"press": {"template": "article"}},
        }
    }
    doc = decode_document(data)
    assert doc.front_matter.extra == {"press": {"template": "article"}}
    assert doc.front_matter.keys.press.declare.acronyms == {"HTML": "HyperText"}
    assert doc.front_matter.keys.press.declare.glossary is None
    assert structural(doc) == data
    assert model.FrontMatter().extra == {}


# --------------------------------------------------------------------------
# Models: equality, hashing, immutability, enums, spans
# --------------------------------------------------------------------------


def test_equality_and_hash_ignore_ids_and_spans() -> None:
    a = model.Str("x", id=1, span=Span(0, 0, 1))
    b = model.Str("x", id=7, span=Span(2, 5, 6))
    assert a == b
    assert hash(a) == hash(b)
    assert a != model.Str("y")
    assert model.Para(content=(a,)) == model.Para(content=(b,))
    assert len({a, b}) == 1


def test_nodes_are_frozen_and_slotted() -> None:
    node = model.Str("x")
    with pytest.raises(AttributeError):
        node.text = "y"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        node.surprise = 1  # type: ignore[attr-defined]
    assert isinstance(node, model.Inline)
    assert isinstance(node, model.Node)
    assert not isinstance(node, model.Block)
    assert model.Str.type == "Str"
    assert model.SpanNode.type == "Span"
    assert model.CommentBlock.type == "Comment" == model.Comment.type


def test_enums_carry_snake_case_values() -> None:
    assert model.ListStyle.LOWER_ALPHA.value == "lower_alpha"
    assert model.ListStyle.GENERIC.value == "generic"
    assert model.Align.LEFT.value == "l"
    assert model.Side.OUTER.value == "outer"
    assert model.OrderedList().style is model.ListStyle.DECIMAL
    assert model.Quoted().kind is model.QuoteKind.DOUBLE


def test_spans_decode_from_triples() -> None:
    space = codec.decode({"type": "Space", "id": 4, "span": [1, 3, 5]}, model.Inline)
    assert space.span == Span(file=1, start=3, end=5)
    assert space.id == 4
    assert codec.encode(space) == {"type": "Space", "id": 4, "span": [1, 3, 5]}
    assert model.SubSpan is Span
    assert Span() == NO_SPAN
    ref = codec.decode(
        {"type": "Ref", "items": [{"key": "k", "key_span": [0, 1, 2]}]}, model.Inline
    )
    assert ref.items[0].key_span == Span(0, 1, 2)
    # An inline tag where a block is expected is refused with the tag's path.
    with pytest.raises(IRDecodeError) as info:
        decode_document({"blocks": [{"type": "Space"}]})
    assert info.value.path == ("blocks", 0, "type")


def test_tagged_unions_for_targets_rows_and_columns() -> None:
    link = codec.decode(
        {"type": "Link", "target": {"type": "Anchor", "value": "fig:x"}}, model.Inline
    )
    assert link.target == model.Anchor(value="fig:x")
    assert codec.encode(link) == {
        "type": "Link",
        "target": {"type": "Anchor", "value": "fig:x"},
        "id": 0,
        "span": [0, 0, 0],
    }
    table = codec.decode(
        {
            "type": "Table",
            "model": {
                "columns": [
                    {"type": "Group", "name": "G", "columns": [{"type": "Leaf", "name": "a"}]}
                ],
                "rows": [{"type": "Separator", "label": "x"}, {"type": "Data", "cells": [{}]}],
            },
        },
        model.Block,
    )
    assert isinstance(table.model.columns[0], model.ColumnGroup)
    assert isinstance(table.model.rows[0], model.Separator)
    cell = table.model.rows[1].cells[0]
    assert cell == model.Cell() and cell.rows == 1 and cell.cols == 1
    assert table.model.settings.width == "auto"
    assert codec.encode(table)["model"]["settings"] == {"width": "auto"}


def test_schema_defaults_are_the_default_instances() -> None:
    """A property with a record-shaped schema default serialises ``Cls()`` to it."""
    schema = json.loads((FIXTURES / "ir.json").read_text(encoding="utf-8"))
    checked = 0

    def ref_class(prop: dict[str, Any]) -> type | None:
        ref = prop.get("$ref") or (prop.get("allOf") or [{}])[0].get("$ref")
        return getattr(model, ref.rsplit("/", 1)[-1]) if ref else None

    def check(properties: dict[str, Any]) -> None:
        nonlocal checked
        for prop in properties.values():
            if isinstance(prop.get("default"), dict):
                cls = ref_class(prop)
                assert cls is not None
                assert codec.encode(cls()) == prop["default"]
                checked += 1

    check(schema["properties"])
    for definition in schema["definitions"].values():
        check(definition.get("properties", {}))
        for variant in definition.get("oneOf", []):
            check(variant.get("properties", {}))
    assert checked >= 4  # front_matter, keys, model, settings


# --------------------------------------------------------------------------
# Decoder errors
# --------------------------------------------------------------------------


def test_decode_errors_name_the_json_path() -> None:
    with pytest.raises(IRDecodeError) as info:
        decode_document({"blocks": [{"type": "Para", "content": [{"type": "Nope"}]}]})
    assert info.value.path == ("blocks", 0, "content", 0, "type")
    assert str(info.value).startswith("$.blocks[0].content[0].type: ")

    with pytest.raises(IRDecodeError) as info:
        decode_document({"blocks": [{"type": "Header"}]})
    assert info.value.path == ("blocks", 0)
    assert "level" in info.value.message

    with pytest.raises(IRDecodeError) as info:
        decode_document({"blocks": [{"type": "Header", "level": "one"}]})
    assert info.value.path == ("blocks", 0, "level")

    with pytest.raises(IRDecodeError) as info:
        decode_document({"blocks": [{"content": []}]})
    assert "tag" in info.value.message

    with pytest.raises(IRDecodeError) as info:
        decode_document({"blocks": [{"type": "OrderedList", "style": "fancy"}]})
    assert info.value.path == ("blocks", 0, "style")


def test_structural_json_may_omit_absent_required_strings() -> None:
    # ``structural`` drops an empty ``src``; decoding the fixture supplies it.
    image = codec.decode({"type": "Image"}, model.Inline)
    assert image.src == ""
    assert codec.encode(image)["src"] == ""


def test_unknown_root_keys_are_ignored_and_versions_checked() -> None:
    doc = decode_document({"tmark": model.TMARK_VERSION, "diagnostics": [], "blocks": []})
    assert doc == model.Document()
    with pytest.raises(IRDecodeError) as info:
        decode_document({"tmark": "99.0.0", "blocks": []})
    assert info.value.path == ("tmark",)
    assert codec._compatible("1.2.3", "1.9.0")
    assert not codec._compatible("2.0.0", "1.9.0")
    assert codec._compatible("0.3.1", "0.3.0")
    assert not codec._compatible("0.4.0", "0.3.0")
    assert codec._compatible("dev", "0.3.0")


# --------------------------------------------------------------------------
# Traversal utilities
# --------------------------------------------------------------------------


def sample() -> model.Document:
    return model.Document(
        blocks=(
            model.Header(level=1, content=(model.Str("Title"),), attrs=model.Attrs(id="t")),
            model.Para(content=(model.Str("Hello"), model.Space(), model.Emph((model.Str("w"),)))),
            model.BulletList(
                items=(
                    model.ListItem(content=(model.Plain(content=(model.Str("one"),)),)),
                    model.ListItem(content=(model.Plain(content=(model.Str("two"),)),)),
                )
            ),
            model.Table(
                model=model.TableModel(
                    rows=(model.DataRow(cells=(model.Cell(content=(model.Str("cell"),)),)),)
                )
            ),
        ),
        footnotes=(model.Footnote(label="1", content=(model.Para(content=(model.Str("foot"),)),)),),
    )


def test_children_and_walk_descend_through_records() -> None:
    doc = sample()
    kids = children(doc)
    assert [type(k).__name__ for k in kids] == ["Header", "Para", "BulletList", "Table", "Para"]
    blist = doc.blocks[2]
    assert all(isinstance(k, model.Plain) for k in children(blist))
    texts = [n.text for n in walk(doc) if isinstance(n, model.Str)]
    assert texts == ["Title", "Hello", "w", "one", "two", "cell", "foot"]
    assert children(model.Str("x")) == ()
    assert list(ir.walk.__wrapped__ if hasattr(ir.walk, "__wrapped__") else []) == []


def test_map_tree_rebuilds_records_and_reuses_unchanged_subtrees() -> None:
    doc = sample()

    def upper(node: model.Node) -> model.Node:
        if isinstance(node, model.Str) and node.text in ("one", "cell"):
            return model.Str(node.text.upper(), id=node.id, span=node.span)
        return node

    mapped = map_tree(doc, upper)
    assert isinstance(mapped, model.Document)
    texts = [n.text for n in walk(mapped) if isinstance(n, model.Str)]
    assert texts == ["Title", "Hello", "w", "ONE", "two", "CELL", "foot"]
    assert mapped.blocks[0] is doc.blocks[0]  # untouched subtree reused
    assert mapped.blocks[1] is doc.blocks[1]
    assert mapped.footnotes is doc.footnotes
    assert mapped.blocks[2] is not doc.blocks[2]
    assert [n.text for n in walk(doc) if isinstance(n, model.Str)][3] == "one"
    assert map_tree(doc, lambda n: n) is doc


def test_map_tree_keeps_ids_and_spans_on_rebuilt_parents() -> None:
    para = model.Para(content=(model.Str("x"),), id=9, span=Span(0, 1, 2))
    mapped = map_tree(para, lambda n: model.Str("y") if isinstance(n, model.Str) else n)
    assert mapped.id == 9 and mapped.span == Span(0, 1, 2)
    assert mapped.content == (model.Str("y"),)


def test_visitor_dispatches_along_the_mro() -> None:
    class Collector(NodeVisitor):
        def __init__(self) -> None:
            self.blocks = 0
            self.texts: list[str] = []

        def visit_Block(self, node: model.Block) -> None:  # noqa: N802
            self.blocks += 1
            self.generic_visit(node)

        def visit_Str(self, node: model.Str) -> None:  # noqa: N802
            self.texts.append(node.text)

    collector = Collector()
    collector.visit(sample())
    # Header, Para, BulletList, 2x Plain, Table, footnote Para
    assert collector.blocks == 7
    assert collector.texts == ["Title", "Hello", "w", "one", "two", "cell", "foot"]
    assert NodeVisitor().visit(sample()) is None


def test_plain_text_matches_tmark() -> None:
    inlines = (
        model.Str("See"),
        model.Space(),
        model.Emph((model.Str("fig"),)),
        model.SoftBreak(),
        model.Code(text="x=1"),
        model.LineBreak(),
        model.Math(text="a^2"),
        model.Ref(items=(model.RefItem(key="k"),)),
        model.Note(label="1"),
        model.Image(src="i.png", alt=(model.Str("alt"),)),
        model.Link(target=model.Url("u"), content=(model.Str("link"),)),
        model.SpanNode(content=(model.Strong((model.Str("!"),)),)),
        model.Abbr(text="HTML"),
        model.Keystroke(keys=("ctrl", "s")),
        model.RawInline(format="latex", text="\\x"),
    )
    assert plain_text(inlines) == "See fig x=1 a^2link!HTML"
    assert plain_text(()) == ""


# --------------------------------------------------------------------------
# Package surface during the transition
# --------------------------------------------------------------------------


def test_the_package_exports_the_generated_model_modules() -> None:
    from texsmith.ir.walk import walk as new_walk

    assert new_walk is walk
    assert ir.model is model
    assert ir.codec is codec
    assert ir.walk.walk is walk  # ``ir.walk`` is the module, not a function


# --------------------------------------------------------------------------
# Optional cross-check against a local tmark wheel (skipped in CI)
# --------------------------------------------------------------------------


def test_against_installed_tmark_wheel() -> None:
    tmark = pytest.importorskip("tmark")
    assert codec.canonical_hash(tmark.schema("ir")) == model.SCHEMA_HASH
    assert codec.wheel_schema_mismatch() is None
    for path in CONFORMANCE[:10]:
        sections = fenced_sections(path.read_text(encoding="utf-8"))
        canonical = sections["canonical"][0][1]
        parsed = tmark.parse(canonical)
        assert "tmark" in parsed
        doc = decode_document(parsed)
        assert structural(doc) == strip_absent(fixture_ir(path)), path.name
        assert encode_document(doc) == {
            k: v for k, v in parsed.items() if k not in ("tmark", "diagnostics")
        }
