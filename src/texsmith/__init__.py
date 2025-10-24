"""Modernised LaTeX rendering package."""

from .bibliography import (
    BibliographyCollection,
    BibliographyIssue,
    DoiBibliographyFetcher,
    DoiLookupError,
    bibliography_data_from_string,
)
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
    "BibliographyCollection",
    "BibliographyIssue",
    "BookConfig",
    "DocumentState",
    "DoiBibliographyFetcher",
    "DoiLookupError",
    "LaTeXConfig",
    "LaTeXFormatter",
    "LaTeXRenderer",
    "RenderContext",
    "RenderPhase",
    "TemplateError",
    "WrappableTemplate",
    "bibliography_data_from_string",
    "copy_template_assets",
    "load_template",
    "renders",
]
