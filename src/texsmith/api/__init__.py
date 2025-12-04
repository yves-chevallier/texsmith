"""Facade aggregating the high-level TeXSmith authoring experience.

Architecture
: `Document` and `DocumentRenderOptions` model the source inputs that travel
  through the conversion pipeline. They encapsulate content, front matter, and
  slot selections independently of the engine internals.
: `convert_documents` together with `RenderSettings` coordinates the conversion
  engine and wraps results in `ConversionBundle` instances exposing convenience
  helpers such as `combined_output`.
: `TemplateSession` and related classes manage higher-level template workflows,
  combining multiple converted fragments into coherent LaTeX projects.

Implementation Rationale
: Providing downstream code with a single import location helps preserve
  backward compatibility. Internal modules can evolve while this facade offers a
  declarative list of supported entry points.
: Concentrating documentation and doctest coverage here guides users toward the
  intended composition patterns when embedding TeXSmith.

Usage Example
:
    >>> from pathlib import Path
    >>> from tempfile import TemporaryDirectory
    >>> from texsmith.api import Document, convert_documents
    >>> with TemporaryDirectory() as tmpdir:
    ...     path = Path(tmpdir) / "example.md"
    ...     _ = path.write_text("# Demo\\nHello")
    ...     bundle = convert_documents([Document.from_markdown(path)])
    ...     [fragment.stem for fragment in bundle.fragments]
    ['example']
"""

from __future__ import annotations

from texsmith.core.user_dir import (
    TexsmithUserDir,
    configure_user_dir,
    get_user_dir,
    user_dir_context,
)

from .document import Document, DocumentRenderOptions, TitleStrategy
from .pipeline import ConversionBundle, LaTeXFragment, RenderSettings, convert_documents
from .service import (
    ConversionRequest,
    ConversionResponse,
    ConversionService,
    SlotAssignment,
    classify_input_source,
)
from .templates import (
    TemplateOptions,
    TemplateRenderResult,
    TemplateSession,
    get_template,
)


__all__ = [
    "ConversionBundle",
    "ConversionRequest",
    "ConversionResponse",
    "ConversionService",
    "Document",
    "DocumentRenderOptions",
    "LaTeXFragment",
    "RenderSettings",
    "SlotAssignment",
    "TemplateOptions",
    "TemplateRenderResult",
    "TemplateSession",
    "TexsmithUserDir",
    "TitleStrategy",
    "classify_input_source",
    "configure_user_dir",
    "convert_documents",
    "get_template",
    "get_user_dir",
    "user_dir_context",
]
