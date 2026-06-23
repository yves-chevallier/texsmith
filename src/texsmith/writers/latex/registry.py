"""The ``@writes`` dispatch registry for IR → LaTeX emitters.

Replaces the magic ``LaTeXFormatter.__getattr__`` template proxy with an
explicit, typed dispatch keyed by IR node class. A node type with no registered
emitter raises a clear, localised error (node type + backend) instead of an
opaque ``AttributeError``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.ir.nodes import Node

    from .writer import LaTeXWriter

NodeT = TypeVar("NodeT", bound="Node")

# Method name -> the IR node class name it emits. Collected at class-creation
# time via the ``@writes`` decorator and resolved against bound methods.
_EMITTER_ATTR = "__ir_writes__"


def writes(
    node_type: type[Node],
) -> Callable[[Callable[[LaTeXWriter, NodeT], str]], Callable[[LaTeXWriter, NodeT], str]]:
    """Mark a writer method as the emitter for ``node_type``.

    Usage::

        @writes(ir.Para)
        def _para(self, node: ir.Para) -> str: ...
    """

    def decorate(
        func: Callable[[LaTeXWriter, NodeT], str],
    ) -> Callable[[LaTeXWriter, NodeT], str]:
        setattr(func, _EMITTER_ATTR, node_type)
        return func

    return decorate


class WriterRegistry:
    """Collects ``@writes``-decorated methods of a writer class."""

    def __init__(self) -> None:
        self._by_type: dict[type, str] = {}

    def collect_from_class(self, cls: type) -> None:
        """Register every ``@writes`` method declared on ``cls`` (and bases).

        Walk the MRO from base to derived so a subclass emitter overrides the
        base emitter for the same node type.
        """
        for klass in reversed(cls.__mro__):
            for name, attr in vars(klass).items():
                node_type = getattr(attr, _EMITTER_ATTR, None)
                if node_type is not None:
                    self._by_type[node_type] = name

    def method_for(self, node: object) -> str | None:
        """Return the emitter method name for ``node`` (by exact type, then MRO)."""
        for klass in type(node).__mro__:
            method = self._by_type.get(klass)
            if method is not None:
                return method
        return None


__all__ = ["WriterRegistry", "writes"]
