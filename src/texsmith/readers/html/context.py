"""Reader context: diagnostics and the recursive lowering callbacks.

A :class:`ReadContext` is threaded through every lowering. It carries the
diagnostic emitter (so an unrecognised construct is *reported*, never dropped)
and exposes the two recursive entry points a handler needs to lower its own
children: :meth:`lower_inline` and :meth:`lower_blocks`. Keeping the recursion
on the context (rather than importing the reader into every handler module)
avoids an import cycle and keeps handlers small and declarative.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable

    from bs4.element import PageElement

    from texsmith.ir.nodes import Block, Inline


class _Lowerer(Protocol):
    """The subset of :class:`HtmlReader` the context delegates back into."""

    def lower_inline(self, children: Iterable[PageElement]) -> tuple[Inline, ...]: ...

    def lower_blocks(self, children: Iterable[PageElement]) -> tuple[Block, ...]: ...


class Diagnostics(Protocol):
    """Minimal emitter shape (matches :class:`core.diagnostics.DiagnosticEmitter`)."""

    def warning(self, message: str, exc: BaseException | None = None) -> None: ...


class ReadContext:
    """Per-read state handed to every lowering."""

    __slots__ = ("_reader", "diagnostics")

    def __init__(self, reader: _Lowerer, diagnostics: Diagnostics) -> None:
        self._reader = reader
        self.diagnostics = diagnostics

    def lower_inline(self, nodes: Iterable[PageElement]) -> tuple[Inline, ...]:
        """Lower a run of HTML children into inline IR nodes."""
        return self._reader.lower_inline(nodes)

    def lower_blocks(self, nodes: Iterable[PageElement]) -> tuple[Block, ...]:
        """Lower a run of HTML children into block IR nodes."""
        return self._reader.lower_blocks(nodes)

    def warn(self, message: str) -> None:
        """Surface a non-fatal reader diagnostic (never silently drop)."""
        self.diagnostics.warning(message)


__all__ = ["Diagnostics", "ReadContext"]
