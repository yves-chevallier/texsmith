"""Transverse writer state for the Typst backend.

The IR is a pure tree; any state the Typst writer needs to thread through a
traversal lives here (mirroring the LaTeX :class:`WriterState`). The Typst
backend now covers a real templated document (article/book), so the state
carries the registries the writer accumulates while traversing the IR:

* ``bibliography`` — keys present in the resolved bibliography collection, used
  to decide whether a footnote-ref / cite resolves to a Typst ``@key`` citation
  or a literal ``#footnote``.
* ``footnotes`` — footnote-definition bodies harvested in a pre-pass, keyed by
  the normalised footnote id (so a ``footnote-ref`` site can resolve its body).
* ``citations`` — ordered, de-duplicated keys actually cited (drives whether the
  scaffolding emits ``#bibliography(...)``).
* ``abbreviations`` — first-seen term -> description (abbr spans).

It does *not* depend on the LaTeX ``DocumentState``: the two backends share the
IR, not their transverse state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TypstWriterState:
    """All transverse state the Typst writer threads through a traversal."""

    title: str = ""
    heading_offset: int = 0
    bibliography: frozenset[str] = field(default_factory=frozenset)
    footnotes: dict[str, str] = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
    abbreviations: dict[str, str] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)

    def record_citation(self, key: str) -> None:
        """Register a citation key once, preserving first-seen order."""
        key = key.strip()
        if key and key not in self.citations:
            self.citations.append(key)


__all__ = ["TypstWriterState"]
