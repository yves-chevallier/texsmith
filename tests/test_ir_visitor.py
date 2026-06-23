"""Unit tests for IR traversal: children, walk, map_tree, NodeVisitor."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

for candidate in (PROJECT_ROOT, SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from texsmith import ir  # noqa: E402
from texsmith.extensions.tables.schema import parse_table  # noqa: E402


def sample_doc() -> ir.Document:
    return ir.Document(
        (
            ir.Header(1, (ir.Str("Title"),), identifier="title"),
            ir.Para((ir.Str("Hello"), ir.Space(), ir.Emph((ir.Str("world"),)))),
            ir.BulletList(
                (
                    (ir.Plain((ir.Str("one"),)),),
                    (ir.Plain((ir.Str("two"),)),),
                )
            ),
        )
    )


# --------------------------------------------------------------------------
# children
# --------------------------------------------------------------------------


def test_children_direct_only() -> None:
    para = ir.Para((ir.Str("a"), ir.Space(), ir.Str("b")))
    kids = ir.children(para)
    assert kids == (ir.Str("a"), ir.Space(), ir.Str("b"))


def test_children_flattens_list_items() -> None:
    blist = ir.BulletList(
        (
            (ir.Plain((ir.Str("x"),)), ir.Para((ir.Str("y"),))),
            (ir.Plain((ir.Str("z"),)),),
        )
    )
    kids = ir.children(blist)
    assert len(kids) == 3
    assert all(isinstance(k, ir.Block) for k in kids)


def test_children_skips_scalar_and_model_fields() -> None:
    # Str has only a scalar field -> no children.
    assert ir.children(ir.Str("x")) == ()
    # Table's embedded model is not a Node -> not traversed as a child.
    model = parse_table({"columns": ["", "n"], "rows": [["a", 1]]})
    table = ir.Table(model=model, caption=(ir.Str("cap"),))
    kids = ir.children(table)
    assert kids == (ir.Str("cap"),)  # only the inline caption, not the model


def test_definition_item_children() -> None:
    item = ir.DefinitionItem(
        term=(ir.Str("term"),),
        definitions=((ir.Plain((ir.Str("def"),)),),),
    )
    dl = ir.DefinitionList((item,))
    assert ir.children(dl) == (item,)
    assert len(ir.children(item)) == 2  # term inline + one definition block


# --------------------------------------------------------------------------
# walk
# --------------------------------------------------------------------------


def test_walk_preorder_visits_every_node() -> None:
    doc = sample_doc()
    nodes = list(ir.walk(doc))
    assert nodes[0] is doc  # root first (pre-order)
    # every Str leaf is reached
    strs = [n.text for n in nodes if isinstance(n, ir.Str)]
    assert strs == ["Title", "Hello", "world", "one", "two"]


def test_walk_count() -> None:
    doc = sample_doc()
    # walking twice is stable
    assert len(list(ir.walk(doc))) == len(list(ir.walk(doc)))


# --------------------------------------------------------------------------
# map_tree
# --------------------------------------------------------------------------


def test_map_tree_rewrites_leaves_bottom_up() -> None:
    doc = sample_doc()

    def upper(node: ir.Node) -> ir.Node:
        if isinstance(node, ir.Str):
            return ir.Str(node.text.upper())
        return node

    mapped = ir.map_tree(doc, upper)
    strs = [n.text for n in ir.walk(mapped) if isinstance(n, ir.Str)]
    assert strs == ["TITLE", "HELLO", "WORLD", "ONE", "TWO"]
    # original tree stays unchanged because nodes are immutable
    orig = [n.text for n in ir.walk(doc) if isinstance(n, ir.Str)]
    assert orig == ["Title", "Hello", "world", "one", "two"]


def test_map_tree_identity_preserves_structure() -> None:
    doc = sample_doc()
    mapped = ir.map_tree(doc, lambda n: n)
    assert mapped == doc


def test_map_tree_can_replace_subtree() -> None:
    doc = ir.Document((ir.Para((ir.Emph((ir.Str("x"),)),)),))

    def deemph(node: ir.Node) -> ir.Node:
        if isinstance(node, ir.Emph):
            return ir.Strong(node.content)
        return node

    mapped = ir.map_tree(doc, deemph)
    inner = mapped.content[0].content[0]
    assert isinstance(inner, ir.Strong)
    assert inner.content[0].text == "x"


# --------------------------------------------------------------------------
# NodeVisitor
# --------------------------------------------------------------------------


def test_visitor_dispatches_by_type() -> None:
    class Collector(ir.NodeVisitor):
        def __init__(self) -> None:
            self.texts: list[str] = []
            self.headers: list[int] = []

        def visit_Str(self, node: ir.Str) -> None:  # noqa: N802
            self.texts.append(node.text)

        def visit_Header(self, node: ir.Header) -> None:  # noqa: N802
            self.headers.append(node.level)
            self.generic_visit(node)  # still descend into the title

    collector = Collector()
    collector.visit(sample_doc())
    assert collector.headers == [1]
    assert collector.texts == ["Title", "Hello", "world", "one", "two"]


def test_visitor_family_handler_via_mro() -> None:
    class BlockCounter(ir.NodeVisitor):
        def __init__(self) -> None:
            self.blocks = 0

        def visit_Block(self, node: ir.Block) -> None:  # noqa: N802
            self.blocks += 1
            self.generic_visit(node)

    counter = BlockCounter()
    counter.visit(sample_doc())
    # Document, Header, Para, BulletList, 2x Plain = 6 blocks
    assert counter.blocks == 6


def test_visitor_generic_visit_default_returns_none() -> None:
    visitor = ir.NodeVisitor()
    # no handlers defined -> generic_visit walks and returns None
    assert visitor.visit(sample_doc()) is None
