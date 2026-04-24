"""Context objects used during document conversion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import BookConfig
from .templates import TemplateBinding


if TYPE_CHECKING:  # pragma: no cover - typing only
    from .bibliography.collection import BibliographyCollection
    from .conversion.models import ConversionRequest
    from .documents import Document
    from .templates.runtime import TemplateRuntime


@dataclass(slots=True)
class AssetMapping:
    """Describe how a source asset should be persisted for LaTeX generation."""

    source: Path
    target: Path
    kind: str | None = None


@dataclass(slots=True)
class GenerationStrategy:
    """Rendering strategy toggles shared across conversion workflows."""

    copy_assets: bool = True
    convert_assets: bool = False
    hash_assets: bool = False
    prefer_inputs: bool = False
    persist_manifest: bool = False


@dataclass(slots=True)
class SegmentContext:
    """Represent a fragment destined for insertion into a template slot."""

    name: str
    html: str
    base_level: int
    metadata: Mapping[str, Any] = field(default_factory=dict)
    bibliography: Mapping[str, Any] = field(default_factory=dict)
    assets: list[AssetMapping] = field(default_factory=list)
    destination: Path | None = None


@dataclass(slots=True)
class ConversionContext:
    """Per-document resolved state for the conversion pipeline.

    The context is built in two successive phases:

    - :func:`resolve_conversion_context` (in :mod:`.conversion.execution`)
      fills the inputs derived from the document, request and front matter.
      At this point :attr:`config` and :attr:`template_binding` are still
      ``None`` because no template has been chosen yet.
    - :func:`bind_template` (in :mod:`.conversion.templates`) resolves the
      selected template and populates the binding-dependent fields.

    Per-slot render flags (``slot_options``) are read from
    ``document.slot_options`` on demand rather than copied here, to avoid
    duplicating state that the :class:`Document` already owns.
    """

    # Resolved inputs (populated by resolve_conversion_context)
    document: Document
    request: ConversionRequest
    output_dir: Path
    language: str
    generation: GenerationStrategy
    template_runtime: TemplateRuntime | None = None
    template_overrides: dict[str, Any] = field(default_factory=dict)
    slot_requests: dict[str, str] = field(default_factory=dict)
    bibliography_collection: BibliographyCollection | None = None
    bibliography_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    runtime_common: dict[str, object] = field(default_factory=dict)

    # Template-bound state (populated by bind_template)
    config: BookConfig | None = None
    template_binding: TemplateBinding | None = None


__all__ = [
    "AssetMapping",
    "ConversionContext",
    "GenerationStrategy",
    "SegmentContext",
]
