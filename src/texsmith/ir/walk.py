"""Traversal utilities over the generated IR (:mod:`texsmith.ir.model`).

Same entry points as :mod:`texsmith.ir.visitor` has for the legacy tree, over
the tmark-shaped models:

* :func:`walk` — every node in pre-order, in tmark's order (``walk.rs``): a
  block before its inlines, ``Para.lead`` before ``content``, an admonition
  title before its body, table rows then footer rows, the document body
  then the footnote definitions.
* :func:`children`, :func:`iter_child_fields` — direct children, found
  structurally: any dataclass field holding a :class:`~texsmith.ir.model.Node`,
  a tuple of them, or a :class:`~texsmith.ir.model.Record` that holds them
  (list items, table cells, footnotes).
* :func:`map_tree` — rebuild bottom-up; ``fn`` sees nodes only, records and
  tuples are rebuilt around them and unchanged subtrees are reused.
* :func:`map_inlines` — rebuild the inline lists: ``fn`` may return one
  inline or a tuple of them (spliced into the parent's list), and ``skip``
  fences off subtrees (a code span, an emoji span) from the rewrite.
* :class:`NodeVisitor` — ``visit_<ClassName>`` double dispatch along the MRO.
* :func:`plain_text` — tmark's ``plain_text``: the text of ``Str``, ``Code``,
  ``Math`` and ``Abbr``, breaks as spaces, formatting containers and links
  descended into, everything else dropped.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import fields, replace
from typing import Any, TypeVar

from texsmith.ir import model
from texsmith.ir.model import Inline, Node, Record


__all__ = [
    "NodeVisitor",
    "children",
    "iter_child_fields",
    "map_inlines",
    "map_tree",
    "plain_text",
    "walk",
]

T = TypeVar("T", bound=Node | Record)


def _holds_nodes(value: Any) -> bool:
    """True if ``value`` is a node or contains one (tuples and records descended)."""
    if isinstance(value, Node):
        return True
    if isinstance(value, tuple):
        return any(_holds_nodes(item) for item in value)
    if isinstance(value, Record):
        return any(_holds_nodes(getattr(value, f.name)) for f in fields(value))
    return False


def iter_child_fields(node: Node | Record) -> Iterator[tuple[str, Any]]:
    """Yield ``(field_name, value)`` for each field holding child node(s).

    Scalar fields, enums, spans and records without nodes (``Attrs``, the
    front matter, ``TableSettings``) are skipped.
    """
    for f in fields(node):
        value = getattr(node, f.name)
        if _holds_nodes(value):
            yield f.name, value


def _iter_nodes(value: Any) -> Iterator[Node]:
    """The nodes directly inside ``value``, through tuples and records."""
    if isinstance(value, Node):
        yield value
    elif isinstance(value, tuple):
        for item in value:
            yield from _iter_nodes(item)
    elif isinstance(value, Record):
        for f in fields(value):
            yield from _iter_nodes(getattr(value, f.name))


def children(node: Node | Record) -> tuple[Node, ...]:
    """The direct child nodes of ``node`` in field order."""
    result: list[Node] = []
    for f in fields(node):
        result.extend(_iter_nodes(getattr(node, f.name)))
    return tuple(result)


def walk(root: Node | Record) -> Iterator[Node]:
    """Yield ``root`` (when it is a node) then every descendant node, pre-order.

    A :class:`~texsmith.ir.model.Document` is not a node: ``walk(doc)`` yields
    its blocks and their descendants, then the footnote contents, as tmark's
    ``walk`` does.
    """
    if isinstance(root, Node):
        yield root
    for child in children(root):
        yield from walk(child)


def _map_value(value: Any, fn: Callable[[Node], Node]) -> Any:
    if isinstance(value, Node):
        return _map_node(value, fn)
    if isinstance(value, tuple):
        items = tuple(_map_value(item, fn) for item in value)
        return value if all(a is b for a, b in zip(items, value, strict=True)) else items
    if isinstance(value, Record):
        return _map_record(value, fn)
    return value


def _map_fields(obj: T, fn: Callable[[Node], Node]) -> T:
    changes: dict[str, Any] = {}
    for name, value in iter_child_fields(obj):
        mapped = _map_value(value, fn)
        if mapped is not value:
            changes[name] = mapped
    return replace(obj, **changes) if changes else obj


def _map_record(record: T, fn: Callable[[Node], Node]) -> T:
    return _map_fields(record, fn)


def _map_node(node: Node, fn: Callable[[Node], Node]) -> Node:
    return fn(_map_fields(node, fn))


def map_tree(root: T, fn: Callable[[Node], Node]) -> T:
    """Return a new tree with ``fn`` applied to every node, bottom-up.

    Children are transformed before their parent, so ``fn`` sees already
    mapped descendants. Nothing is mutated; a subtree ``fn`` returns
    unchanged is reused. ``id`` and ``span`` travel with ``replace``.
    """
    return _map_value(root, fn)


InlineMap = Callable[[Inline], "Inline | tuple[Inline, ...]"]


def _map_inline_value(value: Any, fn: InlineMap, skip: Callable[[Node], bool]) -> Any:
    if isinstance(value, Node):
        if skip(value):
            return value
        rebuilt = _map_inline_fields(value, fn, skip)
        return fn(rebuilt) if isinstance(rebuilt, Inline) else rebuilt
    if isinstance(value, tuple):
        items: list[Any] = []
        changed = False
        for item in value:
            mapped = _map_inline_value(item, fn, skip)
            if isinstance(item, Inline) and isinstance(mapped, tuple):
                items.extend(mapped)
                changed = True
                continue
            if mapped is not item:
                changed = True
            items.append(mapped)
        return tuple(items) if changed else value
    if isinstance(value, Record):
        return _map_inline_fields(value, fn, skip)
    return value


def _map_inline_fields(obj: T, fn: InlineMap, skip: Callable[[Node], bool]) -> T:
    changes: dict[str, Any] = {}
    for name, value in iter_child_fields(obj):
        mapped = _map_inline_value(value, fn, skip)
        if mapped is not value:
            changes[name] = mapped
    return replace(obj, **changes) if changes else obj


def _never(node: Node) -> bool:
    del node
    return False


def map_inlines(
    root: T,
    fn: InlineMap,
    *,
    skip: Callable[[Node], bool] = _never,
) -> T:
    """Return a new tree with ``fn`` applied to every inline, bottom-up.

    Like :func:`map_tree` but for the inline lists: ``fn`` sees every
    :class:`~texsmith.ir.model.Inline` (children first) and returns either a
    replacement inline or a tuple of inlines, which is spliced in place of the
    node in its parent's list (an empty tuple drops it). Blocks and records
    are rebuilt around the changes; ``skip(node)`` fences off a subtree — a
    node it accepts is kept as is, its descendants unseen. Unchanged subtrees
    are reused, ``id`` and ``span`` travel with ``replace``.
    """
    return _map_inline_value(root, fn, skip)


class NodeVisitor:
    """Type-dispatching visitor over the IR.

    Define ``visit_<ClassName>(self, node)`` for the classes you handle;
    :meth:`visit` resolves the method along the node's MRO, so ``visit_Block``
    or ``visit_Inline`` catches a family. Anything unmatched reaches
    :meth:`generic_visit`, which visits the children and returns ``None``.
    """

    def visit(self, node: Node | Record) -> Any:
        """Dispatch to the most specific ``visit_<ClassName>`` for ``node``."""
        for klass in type(node).__mro__:
            method = getattr(self, f"visit_{klass.__name__}", None)
            if method is not None:
                return method(node)
        return self.generic_visit(node)

    def generic_visit(self, node: Node | Record) -> Any:
        """Default: visit each child. Override to customise the fallback."""
        for child in children(node):
            self.visit(child)
        return None


_TEXT = (model.Str, model.Code, model.Math, model.Abbr)
_BREAKS = (model.Space, model.SoftBreak, model.LineBreak)
_THROUGH = (
    model.Emph,
    model.Strong,
    model.Strikeout,
    model.Underline,
    model.Highlight,
    model.Subscript,
    model.Superscript,
    model.SmallCaps,
    model.Quoted,
    model.Link,
    model.SpanNode,
)


def plain_text(inlines: Iterable[Inline]) -> str:
    """The plain text of ``inlines``, as tmark's ``plain_text`` (``walk.rs``).

    ``Str``, ``Code``, ``Math`` and ``Abbr`` contribute their text; ``Space``,
    ``SoftBreak`` and ``LineBreak`` a space; emphasis-like containers, quotes,
    links and spans their content; every other node nothing.
    """
    out: list[str] = []
    for inline in inlines:
        if isinstance(inline, _TEXT):
            out.append(inline.text)
        elif isinstance(inline, _BREAKS):
            out.append(" ")
        elif isinstance(inline, _THROUGH):
            out.append(plain_text(inline.content))
    return "".join(out)
