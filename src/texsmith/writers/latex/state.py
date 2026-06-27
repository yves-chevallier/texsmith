"""Transverse writer state for the LaTeX backend.

The IR is a pure tree; everything that the legacy ``DocumentState`` accumulated
while mutating the soup (citations, acronyms/glossary, footnotes, counters,
index entries, ``requires_shell_escape``, pygments styles, headings/TOC, script
usage, callouts flag) is derived *here*, by the writer, while it traverses the
IR.

:class:`WriterState` deliberately exposes ``runtime`` / ``config`` / ``state`` /
``assets`` / ``formatter`` with the same shape the legacy ``RenderContext`` had,
so the font-script machinery (:mod:`texsmith.fonts.scripts`) and asset helpers
can be reused verbatim — the writer changes *who* calls them, not the helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:  # pragma: no cover - typing only
    from pathlib import Path

    from texsmith.adapters.latex.formatter import LaTeXFormatter
    from texsmith.core.config import BookConfig
    from texsmith.core.context import AssetRegistry, DocumentState


class WriterState:
    """All transverse state the LaTeX writer threads through a traversal."""

    __slots__ = ("assets", "config", "formatter", "runtime", "state")

    def __init__(
        self,
        *,
        state: DocumentState,
        config: BookConfig,
        formatter: LaTeXFormatter,
        assets: AssetRegistry,
        runtime: dict[str, Any],
    ) -> None:
        self.state = state
        self.config = config
        self.formatter = formatter
        self.assets = assets
        self.runtime = runtime

    # -- convenience accessors --------------------------------------------

    @property
    def legacy_accents(self) -> bool:
        """Whether unicode accents should be encoded as legacy LaTeX macros."""
        return bool(getattr(self.config, "legacy_latex_accents", False))

    @property
    def output_root(self) -> Path:
        """Asset output root (used by figure/image emitters)."""
        return self.assets.output_root


__all__ = ["WriterState"]
