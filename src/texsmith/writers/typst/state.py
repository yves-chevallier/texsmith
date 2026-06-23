"""Transverse writer state for the Typst backend.

The IR is a pure tree; any state the Typst writer needs to thread through a
traversal lives here (mirroring the LaTeX :class:`WriterState`). The covered
Typst subset is deliberately small, so the state is correspondingly lean: it
carries the document ``title`` (used by the standalone-document wrapper) and an
opaque ``runtime`` mapping for future options. It does *not* duplicate the
LaTeX state's citation/acronym/footnote registries — those belong to nodes the
Typst backend does not yet cover.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TypstWriterState:
    """All transverse state the Typst writer threads through a traversal."""

    title: str = ""
    runtime: dict[str, Any] = field(default_factory=dict)


__all__ = ["TypstWriterState"]
