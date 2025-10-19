"""High-level HTML to LaTeX renderer based on the modular pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from bs4 import BeautifulSoup, FeatureNotFound

from .config import BookConfig
from .context import AssetRegistry, DocumentState, RenderContext
from .exceptions import LatexRenderingError
from .formatter import LaTeXFormatter
from .rules import RenderEngine, RenderPhase


class LaTeXRenderer:
    """Convert HTML fragments to LaTeX using a modular pipeline."""

    def __init__(
        self,
        config: BookConfig | None = None,
        formatter: LaTeXFormatter | None = None,
        output_root: Path | str = Path("build"),
        parser: str = "lxml",
    ) -> None:
        self.config = config or BookConfig()
        self.formatter = formatter or LaTeXFormatter()
        self.parser_backend = parser

        self.output_root = Path(output_root)
        self.assets_root = (self.output_root / "assets").resolve()
        self.assets_root.mkdir(parents=True, exist_ok=True)

        self.assets = AssetRegistry(self.assets_root)

        # Keep formatter in sync with runtime environment
        self.formatter.config = self.config  # type: ignore[assignment]
        self.formatter.output_path = self.assets_root  # type: ignore[assignment]

        self.engine = RenderEngine()
        self._register_builtin_handlers()

    def _register_builtin_handlers(self) -> None:
        """Register the initial set of handlers for the renderer."""

        from .handlers import (
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

    def render(
        self,
        html: str,
        *,
        runtime: Mapping[str, Any] | None = None,
        state: DocumentState | None = None,
    ) -> str:
        """Render an HTML fragment into LaTeX."""

        try:
            soup = BeautifulSoup(html, self.parser_backend)
        except FeatureNotFound:
            if self.parser_backend == "html.parser":
                raise
            # Fall back to the built-in parser when the preferred backend is missing.
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
