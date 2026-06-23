r"""Traversal utilities for the TeXSmith IR.

Three entry points, all driven by the same child-introspection logic so the
behaviour stays consistent and there is a single source of truth for "what are
a node's children":

* :class:`NodeVisitor` — double-dispatch by node type. Subclass and define
  ``visit_<ClassName>`` methods; unhandled types fall back to
  :meth:`NodeVisitor.generic_visit`.
* :func:`walk` — yield every node in the tree, pre-order (node before its
  descendants).
* :func:`map_tree` — rebuild the tree, applying a function bottom-up. Because
  nodes are frozen dataclasses, mapping returns *new* nodes; the input is never
  mutated.

Child discovery is structural: any dataclass field whose value is a
:class:`~texsmith.ir.nodes.Node`, or a tuple (possibly nested) of nodes, is a
child slot. Scalar fields (text, enums, the embedded tables model, …) are left
alone. This means new node types need no visitor changes as long as they store
children in node/tuple fields.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import fields, is_dataclass, replace
from typing import Any

from texsmith.ir.nodes import Node


__all__ = ["NodeVisitor", "children", "iter_child_fields", "map_tree", "walk"]


def _is_node_container(value: Any) -> bool:
    """True if ``value`` is a node, or a (possibly nested) tuple of nodes."""
    if isinstance(value, Node):
        return True
    if isinstance(value, tuple):
        return any(_is_node_container(item) for item in value)
    return False


def iter_child_fields(node: Node) -> Iterator[tuple[str, Any]]:
    """Yield ``(field_name, value)`` for each field holding child node(s).

    Only fields whose value contains at least one :class:`Node` are yielded;
    scalar fields and non-node objects (e.g. the embedded tables model) are
    skipped.
    """
    if not is_dataclass(node):  # pragma: no cover - defensive
        return
    for f in fields(node):
        value = getattr(node, f.name)
        if _is_node_container(value):
            yield f.name, value


def _iter_nodes(value: Any) -> Iterator[Node]:
    """Flatten a node / nested-tuple-of-nodes into the nodes it contains."""
    if isinstance(value, Node):
        yield value
    elif isinstance(value, tuple):
        for item in value:
            yield from _iter_nodes(item)


def children(node: Node) -> tuple[Node, ...]:
    """Return the direct child nodes of ``node`` in declaration order."""
    result: list[Node] = []
    for _name, value in iter_child_fields(node):
        result.extend(_iter_nodes(value))
    return tuple(result)


def walk(node: Node) -> Iterator[Node]:
    """Yield ``node`` then every descendant, pre-order (depth-first)."""
    yield node
    for child in children(node):
        yield from walk(child)


def _map_value(value: Any, fn: Callable[[Node], Node]) -> Any:
    """Recursively rebuild a field value, mapping any nodes it contains."""
    if isinstance(value, Node):
        return _map_node(value, fn)
    if isinstance(value, tuple):
        return tuple(_map_value(item, fn) for item in value)
    return value


def _map_node(node: Node, fn: Callable[[Node], Node]) -> Node:
    """Map children bottom-up, then apply ``fn`` to the rebuilt node."""
    changes: dict[str, Any] = {}
    for name, value in iter_child_fields(node):
        changes[name] = _map_value(value, fn)
    rebuilt = replace(node, **changes) if changes else node
    return fn(rebuilt)


def map_tree(node: Node, fn: Callable[[Node], Node]) -> Node:
    """Return a new tree with ``fn`` applied to every node, bottom-up.

    Children are transformed before their parent, so ``fn`` sees already-mapped
    descendants. Frozen nodes are never mutated; unchanged subtrees are reused.
    """
    return _map_node(node, fn)


class NodeVisitor:
    """Type-dispatching visitor over the IR.

    Subclass and define ``visit_<ClassName>(self, node)`` for the node types you
    handle. :meth:`visit` resolves the method by walking the node's MRO, so a
    ``visit_Block`` / ``visit_Inline`` handler catches whole families. Anything
    unmatched reaches :meth:`generic_visit`, which by default visits children
    and returns ``None``.
    """

    def visit(self, node: Node) -> Any:
        """Dispatch to the most specific ``visit_<ClassName>`` for ``node``."""
        for klass in type(node).__mro__:
            method = getattr(self, f"visit_{klass.__name__}", None)
            if method is not None:
                return method(node)
        return self.generic_visit(node)

    def generic_visit(self, node: Node) -> Any:
        """Default: visit each child. Override to customise the fallback."""
        for child in children(node):
            self.visit(child)
        return None
