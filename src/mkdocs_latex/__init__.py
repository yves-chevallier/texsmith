"""Modernised LaTeX rendering package."""

from .config import BookConfig, LaTeXConfig
from .context import AssetRegistry, DocumentState, RenderContext
from .formatter import LaTeXFormatter
from .renderer import LaTeXRenderer
from .rules import RenderPhase, renders
from .templates import (
    TemplateError,
    WrappableTemplate,
    copy_template_assets,
    load_template,
)


__all__ = [
    "AssetRegistry",
    "BookConfig",
    "DocumentState",
    "LaTeXConfig",
    "LaTeXFormatter",
    "LaTeXRenderer",
    "RenderContext",
    "RenderPhase",
    "TemplateError",
    "WrappableTemplate",
    "copy_template_assets",
    "load_template",
    "renders",
]
