"""High-level HTML→IR→LaTeX renderer.

``LaTeXRenderer`` is now a thin orchestrator: it parses the HTML fragment into
the typed IR via :class:`texsmith.readers.html.HtmlReader`, then emits LaTeX
from that IR via :class:`texsmith.writers.latex.LaTeXWriter`. The old
mutate-the-soup-and-``get_text`` pipeline (and its phase/handler engine) is
gone — there is a single read→write path.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from texsmith.core.config import BookConfig
from texsmith.core.context import AssetRegistry, DocumentState
from texsmith.core.diagnostics import DiagnosticEmitter, NullEmitter
from texsmith.core.exceptions import LatexRenderingError
from texsmith.readers.html import HtmlReader
from texsmith.writers.latex import LaTeXWriter, WriterState

from .formatter import LaTeXFormatter


class LaTeXRenderer:
    """Convert HTML fragments to LaTeX through the IR (read → write)."""

    def __init__(
        self,
        config: BookConfig | None = None,
        formatter: LaTeXFormatter | None = None,
        output_root: Path | str = Path("build"),
        parser: str = "lxml",
        copy_assets: bool = True,
        convert_assets: bool = False,
        hash_assets: bool = False,
    ) -> None:
        self.config = config or BookConfig()
        self.formatter = formatter or LaTeXFormatter()
        self.parser_backend = parser
        self.copy_assets = copy_assets
        self.convert_assets = convert_assets
        self.hash_assets = hash_assets

        self.output_root = Path(output_root)
        self.assets_root = (self.output_root / "assets").resolve()
        self.assets = AssetRegistry(self.assets_root, copy_assets=self.copy_assets)

        # Keep the formatter in sync with the runtime environment.
        self.formatter.legacy_latex_accents = self.config.legacy_latex_accents

        # The index extension ships an enriched ``index`` partial (registry +
        # styled-entry support). The writer reuses it, so apply the override.
        from texsmith.extensions.index.renderer import INDEX_TEMPLATE

        self.formatter.override_template("index", INDEX_TEMPLATE)

        # Extension hooks: a custom reader registry (extra ``@reads`` lowerings)
        # and/or a ``LaTeXWriter`` subclass (extra ``@writes`` emitters). Left
        # as ``None`` for the default read→write path.
        self.reader_registry: Any | None = None
        self.writer_class: type[LaTeXWriter] = LaTeXWriter

    def register(self, _handler: Any) -> None:
        """Accept legacy handler-registration calls as no-ops.

        Handlers no longer live on the renderer — emission is the writer's job
        (see :mod:`texsmith.writers.latex`). Callers (mkdocs plugin, plugin
        ``register`` helpers) may still invoke this; it is intentionally inert.
        """

    def render(
        self,
        html: str,
        *,
        runtime: Mapping[str, Any] | None = None,
        state: DocumentState | None = None,
        emitter: DiagnosticEmitter | None = None,
    ) -> str:
        """Render an HTML fragment into LaTeX via the IR."""
        active_emitter = emitter or NullEmitter()
        document_state = state or DocumentState()

        merged_runtime: dict[str, Any] = {
            "copy_assets": self.copy_assets,
            "convert_assets": self.convert_assets,
            "hash_assets": self.hash_assets,
            "emitter": active_emitter,
        }
        if runtime:
            merged_runtime.update(dict(runtime))

        from bs4 import FeatureNotFound

        def _make_reader(parser: str) -> HtmlReader:
            return HtmlReader(
                diagnostics=active_emitter, parser=parser, registry=self.reader_registry
            )

        try:
            document = _make_reader(self.parser_backend).read(html)
        except FeatureNotFound:
            # Fall back to the always-available built-in parser, mirroring the
            # legacy renderer's behaviour when the preferred backend is missing.
            self.parser_backend = "html.parser"
            document = _make_reader("html.parser").read(html)
        except Exception as exc:  # pragma: no cover - defensive
            raise LatexRenderingError("HTML reading failed") from exc

        writer_state = WriterState(
            state=document_state,
            config=self.config,
            formatter=self.formatter,
            assets=self.assets,
            runtime=merged_runtime,
        )
        try:
            return self.writer_class(writer_state).write(document)
        except LatexRenderingError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise LatexRenderingError("LaTeX rendering failed") from exc


__all__ = ["LaTeXRenderer"]
