"""High-level HTML to LaTeX renderer based on the modular pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup, FeatureNotFound

from texsmith.core.config import BookConfig
from texsmith.core.context import AssetRegistry, DocumentState, RenderContext
from texsmith.core.diagnostics import DiagnosticEmitter, NullEmitter
from texsmith.core.exceptions import LatexRenderingError
from texsmith.core.rules import RenderEngine, RenderPhase

from .formatter import LaTeXFormatter


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.api.pipeline import ConversionBundle, LaTeXFragment


class LaTeXRenderer:
    _ENTRY_POINT_GROUP = "texsmith.renderers"
    _ENTRY_POINT_PAYLOADS: list[Any] | None = None

    """Convert HTML fragments to LaTeX using a modular pipeline."""

    def __init__(
        self,
        config: BookConfig | None = None,
        formatter: LaTeXFormatter | None = None,
        output_root: Path | str = Path("build"),
        parser: str = "lxml",
        copy_assets: bool = True,
    ) -> None:
        self.config = config or BookConfig()
        self.formatter = formatter or LaTeXFormatter()
        self.parser_backend = parser
        self.copy_assets = copy_assets

        self.output_root = Path(output_root)
        self.assets_root = (self.output_root / "assets").resolve()
        if self.copy_assets:
            self.assets_root.mkdir(parents=True, exist_ok=True)

        self.assets = AssetRegistry(self.assets_root, copy_assets=self.copy_assets)

        # Keep formatter in sync with runtime environment
        self.formatter.config = self.config  # type: ignore[assignment]
        self.formatter.output_path = self.assets_root  # type: ignore[assignment]
        self.formatter.legacy_latex_accents = self.config.legacy_latex_accents

        self.engine = RenderEngine()
        self._register_builtin_handlers()
        self._register_entry_point_handlers()

    def _register_builtin_handlers(self) -> None:
        """Register the initial set of handlers for the renderer."""
        from ..handlers import (
            admonitions as admonition_handlers,
            basic as basic_handlers,
            blocks as block_handlers,
            code as code_handlers,
            inline as inline_handlers,
            links as link_handlers,
            media as media_handlers,
        )

        self.engine.collect_from(basic_handlers)
        self.engine.collect_from(inline_handlers)
        self.engine.collect_from(code_handlers)
        self.engine.collect_from(link_handlers)
        self.engine.collect_from(block_handlers)
        self.engine.collect_from(admonition_handlers)
        self.engine.collect_from(media_handlers)

    def register(self, handler: Any) -> None:
        """Register additional handlers on demand.

        Arguments can be callables decorated with :func:`renders` or modules/classes
        exposing decorated attributes.
        """
        definition = getattr(handler, "__render_rule__", None)
        if definition is not None:
            self.engine.register(handler)
            return

        self.engine.collect_from(handler)

    @classmethod
    def _iter_entry_point_payloads(cls) -> Iterable[Any]:
        if cls._ENTRY_POINT_PAYLOADS is None:
            payloads: list[Any] = []
            try:
                entry_points = metadata.entry_points()
                group = entry_points.select(group=cls._ENTRY_POINT_GROUP)
            except Exception:  # pragma: no cover - defensive
                cls._ENTRY_POINT_PAYLOADS = []
                return ()

            for entry_point in group:
                try:
                    payloads.append(entry_point.load())
                except Exception:  # pragma: no cover - defensive
                    continue
            cls._ENTRY_POINT_PAYLOADS = payloads
        return cls._ENTRY_POINT_PAYLOADS

    def _register_entry_point_handlers(self) -> None:
        for payload in self._iter_entry_point_payloads():
            self._apply_entry_point(payload)

    def _apply_entry_point(self, payload: Any) -> None:
        if callable(payload):
            try:
                payload(self)
                return
            except TypeError:
                self.register(payload)
                return

        register = getattr(payload, "register", None)
        if callable(register):
            register(self)
            return

        self.register(payload)

    def render(
        self,
        html: str,
        *,
        runtime: Mapping[str, Any] | None = None,
        state: DocumentState | None = None,
        emitter: DiagnosticEmitter | None = None,
    ) -> str:
        """Render an HTML fragment into LaTeX."""
        active_emitter = emitter or NullEmitter()
        try:
            soup = BeautifulSoup(html, self.parser_backend)
        except FeatureNotFound:
            if self.parser_backend == "html.parser":
                raise
            # Fall back to the built-in parser when the preferred backend is missing.
            from texsmith.core.conversion.debug import record_event

            record_event(
                active_emitter,
                "parser_fallback",
                {"preferred": self.parser_backend, "fallback": "html.parser"},
            )
            soup = BeautifulSoup(html, "html.parser")
            self.parser_backend = "html.parser"
        document_state = state or DocumentState()

        context = RenderContext(
            config=self.config,
            formatter=self.formatter,
            document=soup,
            assets=self.assets,
            state=document_state,
        )

        context.attach_runtime(copy_assets=self.copy_assets)
        if runtime:
            context.attach_runtime(**runtime)

        try:
            self.engine.run(soup, context)
        except Exception as exc:  # pragma: no cover - defensive
            raise LatexRenderingError("LaTeX rendering failed") from exc

        return self._collect_output(soup)

    def _collect_output(self, soup: BeautifulSoup) -> str:
        """Extract the LaTeX output from the transformed soup."""
        return soup.get_text()

    def iter_registered_rules(self) -> Iterable[tuple[RenderPhase, str]]:
        """Expose currently registered rules for debugging/reporting."""
        for phase in RenderPhase:
            for rule in self.engine.registry.iter_phase(phase):
                yield phase, rule.name


__all__ = ["LaTeXRenderer"]
