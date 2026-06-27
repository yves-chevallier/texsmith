"""Diagram rendering for the Typst backend.

The LaTeX backend renders Draw.io / Mermaid diagrams to PDF inside its
writer/media stage (:mod:`texsmith.writers.latex.media`). The Typst backend
consumes the IR directly, where those diagrams survive as either:

* a :class:`~texsmith.ir.nodes.CodeBlock` with ``lang == "mermaid"`` (a fenced
  ``mermaid`` block, or a decoded ``mermaid.live`` link), or
* an :class:`~texsmith.ir.nodes.Image` pointing at a ``.drawio`` / ``.mmd`` file.

Typst cannot read ``.drawio`` / ``.mmd`` natively, so this module runs a
pre-pass that converts each diagram to a PNG (reusing the shared converter
strategies) and rewrites the IR node to reference the rendered image. The
returned ``image_map`` additions wire those PNGs into the writer's resolution
map. Conversion failures degrade gracefully — the original node is kept so the
document still emits (the writer then drops an unresolved image, exactly as it
does for any other missing asset).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from texsmith.ir import nodes as ir
from texsmith.ir.visitor import map_tree


_MERMAID_SUFFIXES = {".mmd", ".mermaid"}
_DRAWIO_SUFFIXES = {".drawio", ".dio"}


def render_diagrams(
    document: ir.Document,
    *,
    source_dir: Path,
    output_dir: Path | None,
    backend: str | None = None,
    emitter: Any = None,
) -> tuple[ir.Document, dict[str, str]]:
    """Convert diagram nodes to PNGs, returning ``(new_document, image_map)``.

    ``image_map`` maps each rewritten image ``src`` to the PNG filename emitted
    next to the ``.typ`` (the writer copies/resolves nothing further for these).
    """
    image_map: dict[str, str] = {}
    if output_dir is None:
        return document, image_map

    def transform(node: ir.Node) -> ir.Node:
        if isinstance(node, ir.CodeBlock) and node.lang.strip().lower() == "mermaid":
            return _mermaid_block(
                node, output_dir=output_dir, backend=backend, emitter=emitter, image_map=image_map
            )
        if isinstance(node, ir.Image):
            return _diagram_image(
                node,
                source_dir=source_dir,
                output_dir=output_dir,
                backend=backend,
                emitter=emitter,
                image_map=image_map,
            )
        return node

    return map_tree(document, transform), image_map


def _mermaid_block(
    node: ir.CodeBlock,
    *,
    output_dir: Path,
    backend: str | None,
    emitter: Any,
    image_map: dict[str, str],
) -> ir.Node:
    """Render a ``mermaid`` code block to a PNG figure/image node."""
    caption, body = _split_mermaid_caption(node.text)
    png = _convert_mermaid(body, output_dir=output_dir, backend=backend, emitter=emitter)
    if png is None:
        return node  # graceful: keep the original block
    image_map[png] = png
    image = ir.Image(src=png)
    if caption:
        return ir.Figure(content=(ir.Plain(content=(image,)),), caption=(ir.Str(caption),))
    return ir.Plain(content=(image,))


def _diagram_image(
    node: ir.Image,
    *,
    source_dir: Path,
    output_dir: Path,
    backend: str | None,
    emitter: Any,
    image_map: dict[str, str],
) -> ir.Node:
    """Rewrite a ``.drawio`` / ``.mmd`` image to a rendered PNG (else unchanged)."""
    suffix = Path(node.src).suffix.lower()
    if suffix in _DRAWIO_SUFFIXES:
        source = (source_dir / node.src).resolve()
        if not source.is_file():
            return node
        png = _convert_drawio(source, output_dir=output_dir, backend=backend, emitter=emitter)
    elif suffix in _MERMAID_SUFFIXES:
        source = (source_dir / node.src).resolve()
        if not source.is_file():
            return node
        body = source.read_text("utf-8")
        png = _convert_mermaid(body, output_dir=output_dir, backend=backend, emitter=emitter)
    else:
        return node

    if png is None:
        return node
    image_map[png] = png
    from dataclasses import replace

    return replace(node, src=png)


def _convert_mermaid(
    content: str, *, output_dir: Path, backend: str | None, emitter: Any
) -> str | None:
    from texsmith.adapters.transformers import mermaid2pdf

    try:
        produced = mermaid2pdf(
            content, output_dir, format="png", backend=backend or "auto", emitter=emitter
        )
    except Exception:  # diagram toolchain unavailable -> degrade gracefully
        return None
    return Path(produced).name


def _convert_drawio(
    source: Path, *, output_dir: Path, backend: str | None, emitter: Any
) -> str | None:
    from texsmith.adapters.transformers import drawio2pdf

    try:
        produced = drawio2pdf(
            source, output_dir, format="png", backend=backend or "auto", emitter=emitter
        )
    except Exception:  # diagram toolchain unavailable -> degrade gracefully
        return None
    return Path(produced).name


def _split_mermaid_caption(diagram: str) -> tuple[str | None, str]:
    """Pull a caption from a leading ``%%`` comment (mirrors the LaTeX backend)."""
    lines = diagram.splitlines()
    if lines and lines[0].strip().startswith("%%"):
        caption = lines[0].strip()[2:].strip() or None
        return caption, "\n".join(lines[1:])
    return None, diagram


__all__ = ["render_diagrams"]
