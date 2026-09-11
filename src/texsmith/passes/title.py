"""The ``title`` pass: apply the title decision of ``prepare_for_conversion``.

Decision X1: title promotion removes a block, so it runs before
``tmark.resolve``. The decision itself is taken on the whole document by
:meth:`Document.prepare_for_conversion` — ``PROMOTE_METADATA`` when the first
top-level header is unique at its level and the front matter declares no
title (``title: null`` opts out, since ``front_matter_has_title`` sees it as
absent but the strategy is resolved with the declared key), ``DROP`` for
``--strip-heading``. This pass only drops that first top-level ``Header``
when :attr:`Document.drop_title` says so; ``extracted_title`` was recorded
by ``prepare_for_conversion``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from texsmith.ir import model
from texsmith.passes import PassContext, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


@spec("title", after=("var",))
def run(document: Document, ctx: PassContext) -> Document:
    del ctx
    ir_document = document.ir
    if ir_document is None or not document.drop_title:
        return document
    blocks = ir_document.blocks
    for index, block in enumerate(blocks):
        if isinstance(block, model.Header):
            remaining = (*blocks[:index], *blocks[index + 1 :])
            return document.evolve(ir=replace(ir_document, blocks=remaining))
    return document
