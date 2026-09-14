"""The ``var`` pass: body moustaches → text (``python-ir-and-passes.md`` §5).

``Var{path}`` nodes are substituted by a dotted lookup in ``ctx.contexts``
(template overrides, front matter, the mustache defaults — first context
defining the full path wins, as ``replace_mustaches`` does). A scalar becomes
``Str(str(value))`` with the source span and a fresh id (span rule 2); a list
or a mapping emits ``var-not-scalar``; a missing path (or ``None``, or an
empty string — the legacy rule) leaves the ``Var``, emits ``var-unresolved``
at its span, and the writers print the moustache verbatim. No skip-tag logic:
the parser never forms a ``Var`` inside code, math or raw.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from tmark.ir import model
from tmark.ir.walk import map_tree

from texsmith.passes import PassContext, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


_MISSING = object()


def lookup(path: Sequence[str], contexts: Sequence[Mapping[str, Any] | None]) -> Any:
    """The value of the dotted ``path`` in the first context that defines it, else ``_MISSING``."""
    for context in contexts:
        current: Any = context
        for part in path:
            if not isinstance(current, Mapping) or part not in current:
                current = _MISSING
                break
            current = current[part]
        if current is not _MISSING:
            return current
    return _MISSING


@spec("var")
def run(document: Document, ctx: PassContext) -> Document:
    if document.ir is None:
        return document
    contexts = ctx.contexts

    def substitute(node: model.Node) -> model.Node:
        if not isinstance(node, model.Var):
            return node
        moustache = "{{" + ".".join(node.path) + "}}"
        value = lookup(node.path, contexts)
        if value is _MISSING or value is None or (isinstance(value, str) and not value.strip()):
            ctx.diagnostics.emit(
                "var-unresolved",
                node.span,
                f"unresolved moustache '{moustache}'; left as written",
            )
            return node
        if isinstance(value, Mapping) or (
            isinstance(value, Sequence) and not isinstance(value, str | bytes)
        ):
            ctx.diagnostics.emit(
                "var-not-scalar",
                node.span,
                f"moustache '{moustache}' resolves to a {type(value).__name__}, not a scalar",
            )
            return node
        return model.Str(text=str(value), id=ctx.ids.next(), span=node.span)

    rebuilt = map_tree(document.ir, substitute)
    if rebuilt is document.ir:
        return document
    return document.evolve(ir=rebuilt)
