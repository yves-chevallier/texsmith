"""The ``snippet`` pass: a ``.snippet`` fence becomes its rendered preview (``writers-and-passes.md`` §3 row 4).

A :class:`~tmark.ir.model.CodeBlock` whose info string carries the
``snippet`` class (```` ```markdown {.snippet caption="…" width="60%"} ````,
a YAML fence naming ``sources``, or a ``config=`` file) is rendered by the
legacy snippet compiler — :func:`~texsmith.adapters.plugins.snippet.build_snippet_block`
parses the fence, :func:`~texsmith.adapters.plugins.snippet.ensure_snippet_assets`
runs the nested conversion + LaTeX build (or serves the content-hash cache)
and writes the PDF/PNG pair into ``<output dir>/snippets/``. The fence is
replaced by ``Figure{Para{Image}, Caption?}``: the image ``src`` is the
absolute path of the rendered PDF (the PNG for the Typst backend), which the
``assets`` pass that follows stores under ``<output dir>/assets`` and
rewrites to the output-relative path like any local image; ``width=``
travels as the image attribute, ``caption=`` becomes a figure caption and
``label=`` (or the fence's ``#id``) the anchor. The figure keeps the fence's
id and span; the nodes created inside share the span and take fresh ids.

A fence that cannot be parsed or built stays in place as code with
``snippet-build-failed`` at its span — nothing raises out of the pass.
Tests replace :func:`render_snippet_assets` with a fake renderer.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from tmark.ir import model
from tmark.ir.walk import map_tree

from texsmith.adapters.plugins.snippet import (
    FENCE_ATTRIBUTES,
    SNIPPET_DIR,
    SnippetAssets,
    SnippetBlock,
    build_snippet_block,
    ensure_snippet_assets,
)
from texsmith.diagnostics import DiagnosticEmitter
from texsmith.passes import PassContext, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


__all__ = ["SNIPPET_CLASS", "render_snippet_assets", "run"]

#: The fence class that marks a snippet preview.
SNIPPET_CLASS = "snippet"


def render_snippet_assets(
    block: SnippetBlock,
    *,
    output_dir: Path,
    source_path: Path,
    emitter: DiagnosticEmitter | None,
) -> SnippetAssets:
    """Render (or fetch from the cache) the PDF/PNG pair of ``block`` under ``output_dir``.

    The one I/O seam of the pass: the legacy compiler behind it, replaced by a
    fake in the fixture tests.
    """
    return ensure_snippet_assets(
        block, output_dir=output_dir, source_path=source_path, emitter=emitter
    )


def _fence_attributes(block: model.CodeBlock) -> dict[str, Any]:
    """The snippet attributes of a fence: its ``key=value`` options and the ``#id`` as ``label``."""
    attributes: dict[str, Any] = {
        key: value for key, value in block.options.kv if key in FENCE_ATTRIBUTES
    }
    if block.options.id and not attributes.get("label"):
        attributes["label"] = block.options.id
    return attributes


class _Renderer:
    """One pass over one document: fences to figures, failures to diagnostics."""

    __slots__ = ("ctx", "host")

    def __init__(self, ctx: PassContext, host: Path) -> None:
        self.ctx = ctx
        self.host = host

    def rewrite(self, node: model.Node) -> model.Node:
        if not isinstance(node, model.CodeBlock) or SNIPPET_CLASS not in node.options.classes:
            return node
        try:
            block = build_snippet_block(
                node.text,
                language=node.lang,
                attributes=_fence_attributes(node),
                host_path=self.host,
            )
            if block is None:
                return self._failed(node, "the fence has neither inline content nor sources")
            assets = render_snippet_assets(
                block,
                output_dir=self.ctx.output_dir / SNIPPET_DIR,
                source_path=self.host,
                emitter=self.ctx.emitter,
            )
        except Exception as exc:  # a failed nested build never escapes a pass
            return self._failed(node, str(exc))
        return self._figure(node, block, assets)

    def _failed(self, node: model.CodeBlock, reason: str) -> model.CodeBlock:
        self.ctx.diagnostics.emit(
            "snippet-build-failed",
            node.span,
            f"snippet build failed: {reason}",
        )
        return node

    def _figure(
        self, node: model.CodeBlock, block: SnippetBlock, assets: SnippetAssets
    ) -> model.Figure:
        ids = self.ctx.ids
        span = node.span
        source = assets.pdf
        caption = block.caption
        image = model.Image(
            src=Path(source).resolve().as_posix(),
            alt=(model.Str(text=caption, id=ids.next(), span=span),) if caption else (),
            attrs=model.Attrs(kv=(("width", block.figure_width),) if block.figure_width else ()),
            id=ids.next(),
            span=span,
        )
        content: list[model.Block] = [model.Para(content=(image,), id=ids.next(), span=span)]
        figure_attrs = model.Attrs()
        if caption:
            content.append(
                model.Caption(
                    kind=model.CaptionKind.FIGURE,
                    attrs=model.Attrs(id=block.label),
                    content=(model.Str(text=caption, id=ids.next(), span=span),),
                    id=ids.next(),
                    span=span,
                )
            )
        else:
            figure_attrs = model.Attrs(id=block.label)
        return model.Figure(attrs=figure_attrs, content=tuple(content), id=node.id, span=span)


def _host_of(document: Document, ctx: PassContext) -> Path:
    ir = document.ir
    if ir is not None and ir.file in ctx.files:
        return Path(ctx.files.path(ir.file))
    return Path(document.source_path)


@spec("snippet", stage="pre", after=("include",), needs_io=True)
def run(document: Document, ctx: PassContext) -> Document:
    ir = document.ir
    if ir is None:
        return document
    rebuilt = map_tree(ir, _Renderer(ctx, _host_of(document, ctx)).rewrite)
    if rebuilt is ir:
        return document
    return document.evolve(ir=rebuilt)
