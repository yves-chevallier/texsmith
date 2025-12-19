"""Primary public API for TeXSmith."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

from texsmith import _alias as _legacy_aliases
from texsmith.api import (
    ConversionBundle,
    ConversionRequest,
    ConversionResponse,
    ConversionService,
    Document,
    DocumentRenderOptions,
    LaTeXFragment,
    RenderSettings,
    SlotAssignment,
    TemplateOptions,
    TemplateRenderResult,
    TemplateSession,
    TitleStrategy,
    classify_input_source,
    convert_documents,
    get_template,
)
from texsmith.core.bibliography import (
    BibliographyCollection,
    BibliographyIssue,
    DoiBibliographyFetcher,
    DoiLookupError,
    bibliography_data_from_string,
)
from texsmith.core.config import BookConfig, LaTeXConfig
from texsmith.core.context import AssetRegistry, DocumentState, RenderContext
from texsmith.core.rules import RenderPhase, renders
from texsmith.core.templates import (
    DEFAULT_TEMPLATE_LANGUAGE,
    TemplateBinding,
    TemplateError,
    TemplateRuntime,
    TemplateSlot,
    WrappableTemplate,
    build_template_overrides,
    copy_template_assets,
    load_template,
    load_template_runtime,
    resolve_template_language,
)
from texsmith.core.user_dir import (
    TexsmithUserDir,
    configure_user_dir,
    get_user_dir,
    user_dir_context,
)


try:
    __version__ = _pkg_version("texsmith")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "DEFAULT_TEMPLATE_LANGUAGE",
    "AssetRegistry",
    "BibliographyCollection",
    "BibliographyIssue",
    "BookConfig",
    "ConversionBundle",
    "ConversionRequest",
    "ConversionResponse",
    "ConversionService",
    "Document",
    "DocumentRenderOptions",
    "DocumentState",
    "DoiBibliographyFetcher",
    "DoiLookupError",
    "LaTeXConfig",
    "LaTeXFragment",
    "RenderContext",
    "RenderPhase",
    "RenderSettings",
    "SlotAssignment",
    "TemplateBinding",
    "TemplateError",
    "TemplateOptions",
    "TemplateRenderResult",
    "TemplateRuntime",
    "TemplateSession",
    "TemplateSlot",
    "TexsmithUserDir",
    "TitleStrategy",
    "WrappableTemplate",
    "__version__",
    "bibliography_data_from_string",
    "build_template_overrides",
    "classify_input_source",
    "configure_user_dir",
    "convert_documents",
    "copy_template_assets",
    "get_template",
    "get_user_dir",
    "load_template",
    "load_template_runtime",
    "renders",
    "resolve_template_language",
    "user_dir_context",
]
