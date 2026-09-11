"""The ``assets`` pass — registered no-op, not implemented in this wave.

TODO(migration 3.3): diagram and image conversion, remote fetches, src rewriting.
Until then the pass returns its input unchanged; ``tests/passes/test_stubs.py``
asserts that.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from texsmith.passes import PassContext, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


@spec("assets", stage="pre", needs_io=True)
def run(document: Document, ctx: PassContext) -> Document:
    del ctx
    return document
