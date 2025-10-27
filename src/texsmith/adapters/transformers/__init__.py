"""Conversion registry exposing high-level helpers for assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from texsmith.core.exceptions import TransformerExecutionError

from .base import ConverterStrategy
from .strategies import (
    DrawioToPdfStrategy,
    FetchImageStrategy,
    ImageToPdfStrategy,
    MermaidToPdfStrategy,
    PdfMetadataStrategy,
    SvgToPdfStrategy,
)


class ConverterRegistry:
    """Registry storing converter strategies."""

    def __init__(self) -> None:
        self._strategies: dict[str, ConverterStrategy] = {}

    def register(self, name: str, strategy: ConverterStrategy) -> None:
        """Register a converter strategy under a unique name."""
        self._strategies[name] = strategy

    def get(self, name: str) -> ConverterStrategy:
        """Return a registered converter strategy or raise an execution error."""
        try:
            return self._strategies[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise TransformerExecutionError(f"No converter registered for '{name}'") from exc

    def is_registered(self, name: str) -> bool:
        """Return True when a converter has been registered under the given name."""
        return name in self._strategies

    def convert(
        self,
        name: str,
        source: Path | str,
        *,
        output_dir: Path,
        **options: Any,
    ) -> Any:
        """Execute a converter strategy with the provided arguments."""
        strategy = self.get(name)
        return strategy(source, output_dir=output_dir, **options)


registry = ConverterRegistry()

# Built-in strategies
registry.register("svg", SvgToPdfStrategy())
registry.register("image", ImageToPdfStrategy())
registry.register("fetch-image", FetchImageStrategy())
registry.register("pdf-metadata", PdfMetadataStrategy())
registry.register("drawio", DrawioToPdfStrategy())
registry.register("mermaid", MermaidToPdfStrategy())


def register_converter(name: str, strategy: ConverterStrategy) -> None:
    """Expose a helper to register external strategies."""
    registry.register(name, strategy)


def has_converter(name: str) -> bool:
    """Return True when a converter strategy is currently registered."""
    return registry.is_registered(name)


def svg2pdf(source: Path | str, output_dir: Path, **options: Any) -> Path:
    """Convert SVG assets to PDF."""
    return registry.convert("svg", source, output_dir=output_dir, **options)


def image2pdf(source: Path | str, output_dir: Path, **options: Any) -> Path:
    """Convert bitmap images to PDF."""
    return registry.convert("image", source, output_dir=output_dir, **options)


def drawio2pdf(source: Path | str, output_dir: Path, **options: Any) -> Path:
    """Convert draw.io diagrams to PDF."""
    return registry.convert("drawio", source, output_dir=output_dir, **options)


def mermaid2pdf(source: Path | str, output_dir: Path, **options: Any) -> Path:
    """Convert Mermaid diagrams to PDF."""
    return registry.convert("mermaid", source, output_dir=output_dir, **options)


def fetch_image(url: str, output_dir: Path, **options: Any) -> Path:
    """Fetch a remote image and normalise it to PDF."""
    return registry.convert("fetch-image", url, output_dir=output_dir, **options)


def get_pdf_page_sizes(source: Path | str, **options: Any) -> dict[str, Any]:
    """Inspect a PDF and return structured metadata."""
    output_dir = options.pop(
        "output_dir", Path(source).parent if isinstance(source, Path) else Path.cwd()
    )
    return registry.convert("pdf-metadata", source, output_dir=output_dir, **options)


__all__ = [
    "ConverterRegistry",
    "ConverterStrategy",
    "DrawioToPdfStrategy",
    "MermaidToPdfStrategy",
    "drawio2pdf",
    "fetch_image",
    "get_pdf_page_sizes",
    "has_converter",
    "image2pdf",
    "mermaid2pdf",
    "register_converter",
    "svg2pdf",
]
