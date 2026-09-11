"""The ``include`` pass: splice included files into the IR (``writers-and-passes.md`` §3 row 1).

Two forms, both consumed here so that ``tmark.resolve`` sees one document and
``Resolved.included`` stays empty:

* ``{include}(file)`` — a :class:`~texsmith.ir.model.Include` block (the
  deprecated ``--8<-- "file"`` line parses to the same node). The file is
  loaded through ``ctx.loader`` relative to the including file (``base=``
  names the directory the path is looked up in instead), registered in
  ``ctx.files``, parsed with ``tmark.parse(..., file_id=…)`` so its spans keep
  their own :class:`~texsmith.diagnostics.FileId`, its ids re-keyed above the
  allocator floor, and its blocks spliced in place. Footnote and abbreviation
  definitions of the included file join the host's; nested includes recurse
  depth-first with a cycle guard (``include-cycle``); relative ``Image.src``
  and fence ``include=`` paths of the included file are rebased to the main
  document's directory (spec §Includes: they resolve against the included
  file's own directory).
* a fenced block with ``include="file"`` (``pymdownx.snippets`` inside a
  fence, which the parser turns into exactly this option) takes the file's
  text, read relative to the file the fence sits in; the option is consumed.

A file that cannot be loaded becomes the visible literal
``Para([Str("[include: x not found]")])`` (a code fence keeps the literal as
its text) with ``include-missing`` at the node's span, tmark's own message.
"""

from __future__ import annotations

from dataclasses import fields, replace
import os
from pathlib import Path, PurePath
import posixpath
import re
from typing import TYPE_CHECKING, Any, TypeVar

import tmark

from texsmith.ir import codec, model
from texsmith.ir.model import Node, Record
from texsmith.ir.walk import map_tree
from texsmith.passes import PassContext, diagnostic_span, highest_id, spec
from texsmith.readers.loader import join


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


__all__ = ["rebase_path", "run", "shift_ids"]

T = TypeVar("T")

_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def rebase_path(path: str, prefix: str) -> str:
    """``path`` written relative to a directory ``prefix`` deeper (or aside); URLs and absolute paths stay."""
    if not path or prefix in ("", "."):
        return path
    if _SCHEME.match(path) or path.startswith(("/", "\\")) or PurePath(path).is_absolute():
        return path
    return posixpath.normpath(posixpath.join(prefix, path))


def _relative_prefix(included: str, origin: str) -> str:
    """The directory of ``included`` relative to the directory of ``origin``, POSIX spelled."""
    included_dir = str(PurePath(included).parent)
    origin_dir = str(PurePath(origin).parent)
    try:
        prefix = os.path.relpath(included_dir, origin_dir)
    except ValueError:  # pragma: no cover - two Windows drives
        return Path(included_dir).as_posix()
    return Path(prefix).as_posix()


def shift_ids(value: T, delta: int) -> T:
    """``value`` with every node id (and record id: footnotes, abbreviations) raised by ``delta``."""
    if isinstance(value, Node | Record):
        changes: dict[str, Any] = {}
        for f in fields(value):
            item = getattr(value, f.name)
            if f.name == "id" and isinstance(item, int) and not isinstance(item, bool):
                changes[f.name] = item + delta
            else:
                shifted = shift_ids(item, delta)
                if shifted is not item:
                    changes[f.name] = shifted
        return replace(value, **changes) if changes else value
    if isinstance(value, tuple):
        items = tuple(shift_ids(item, delta) for item in value)
        return value if all(a is b for a, b in zip(items, value, strict=True)) else items  # type: ignore[return-value]
    return value


def _rebase_tree(root: T, prefix: str) -> T:
    """Rebase the relative paths of ``root`` (``Image.src``, fence ``include=``, ``Include``)."""
    if prefix in ("", "."):
        return root

    def rebase(node: Node) -> Node:
        if isinstance(node, model.Image):
            src = rebase_path(node.src, prefix)
            return node if src == node.src else replace(node, src=src)
        if isinstance(node, model.CodeBlock):
            kv = tuple(
                (key, rebase_path(value, prefix) if key == "include" else value)
                for key, value in node.options.kv
            )
            if kv == node.options.kv:
                return node
            return replace(node, options=replace(node.options, kv=kv))
        if isinstance(node, model.Include):
            if node.base is not None:
                return replace(node, base=rebase_path(node.base, prefix))
            return replace(node, path=rebase_path(node.path, prefix))
        return node

    return map_tree(root, rebase)


def _option(attrs: model.Attrs, key: str) -> str | None:
    for name, value in attrs.kv:
        if name == key:
            return value
    return None


class _Splicer:
    """One pass over one document; collects the definitions the included files bring."""

    __slots__ = ("abbreviations", "ctx", "footnotes")

    def __init__(self, ctx: PassContext) -> None:
        self.ctx = ctx
        self.footnotes: list[model.Footnote] = []
        self.abbreviations: list[model.AbbrDef] = []

    def expand(self, value: T, origin: str, chain: frozenset[str]) -> T:
        """``value`` with every ``Include`` spliced and every fence ``include=`` read.

        ``origin`` is the file the nodes come from (paths resolve against its
        directory); ``chain`` the files being expanded, for the cycle guard.
        """
        if isinstance(value, tuple):
            out: list[Any] = []
            changed = False
            for item in value:
                if isinstance(item, model.Include):
                    out.extend(self._splice(item, origin, chain))
                    changed = True
                    continue
                expanded = self.expand(item, origin, chain)
                changed = changed or expanded is not item
                out.append(expanded)
            return tuple(out) if changed else value  # type: ignore[return-value]
        if isinstance(value, model.CodeBlock):
            return self._code_block(value, origin)  # type: ignore[return-value]
        if isinstance(value, Node | Record):
            changes: dict[str, Any] = {}
            for f in fields(value):
                item = getattr(value, f.name)
                if isinstance(item, tuple | Node | Record):
                    expanded = self.expand(item, origin, chain)
                    if expanded is not item:
                        changes[f.name] = expanded
            return replace(value, **changes) if changes else value
        return value

    def _literal(self, text: str, span: model.Span) -> model.Para:
        return model.Para(
            content=(model.Str(text=text, id=self.ctx.ids.next(), span=span),),
            id=self.ctx.ids.next(),
            span=span,
        )

    def _splice(
        self, include: model.Include, origin: str, chain: frozenset[str]
    ) -> tuple[model.Block, ...]:
        rel = include.path
        from_path = join(origin, include.base) if include.base else origin
        target = join(from_path, rel)
        span = diagnostic_span(include.span)
        if target in chain:
            self.ctx.diagnostics.emit(
                "include-cycle",
                span,
                f"included file `{rel}` is already being included; skipped",
            )
            return (self._literal(f"[include: {rel} skipped, cycle]", include.span),)

        text = self.ctx.loader.load(from_path, rel)
        if text is None:
            self.ctx.diagnostics.emit("include-missing", span, f"included file `{rel}` not found")
            return (self._literal(f"[include: {rel} not found]", include.span),)

        file_id = self.ctx.files.find(target)
        if file_id is None:
            file_id = self.ctx.files.add(target, text)
        payload = tmark.parse(text, file=target, file_id=int(file_id))
        self.ctx.diagnostics.extend_from_tmark(payload.get("diagnostics") or ())
        included = codec.decode_document(payload)

        # Ids: the included file numbers from 1; move them into a fresh range.
        included = shift_ids(included, self.ctx.ids.reserve(highest_id(included) + 1))
        # Nested includes and fence includes resolve against the included file.
        included = self.expand(included, target, chain | {target})
        # Then everything relative to it is rewritten relative to ``origin``.
        included = _rebase_tree(included, _relative_prefix(target, origin))

        self.footnotes.extend(included.footnotes)
        self.abbreviations.extend(included.abbreviations)
        return included.blocks

    def _code_block(self, block: model.CodeBlock, origin: str) -> model.CodeBlock:
        rel = _option(block.options, "include")
        if rel is None:
            return block
        options = replace(
            block.options, kv=tuple(item for item in block.options.kv if item[0] != "include")
        )
        text = self.ctx.loader.load(origin, rel)
        if text is None:
            self.ctx.diagnostics.emit(
                "include-missing",
                diagnostic_span(block.span),
                f"included file `{rel}` not found",
            )
            return replace(block, text=f"[include: {rel} not found]", options=options)
        return replace(block, text=text, options=options)


def _origin_of(document: Document, ctx: PassContext) -> str:
    ir = document.ir
    if ir is not None and ir.file in ctx.files:
        return str(ctx.files.path(ir.file))
    return str(document.source_path)


@spec("include", stage="pre", needs_io=True)
def run(document: Document, ctx: PassContext) -> Document:
    ir = document.ir
    if ir is None:
        return document
    origin = _origin_of(document, ctx)
    splicer = _Splicer(ctx)
    expanded = splicer.expand(ir, origin, frozenset({origin}))
    if expanded is ir and not splicer.footnotes and not splicer.abbreviations:
        return document
    rebuilt = replace(
        expanded,
        footnotes=(*expanded.footnotes, *splicer.footnotes),
        abbreviations=(*expanded.abbreviations, *splicer.abbreviations),
    )
    return document.evolve(ir=rebuilt)
