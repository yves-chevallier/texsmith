"""Execution context data model shared across conversion pipelines."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .bibliography.collection import BibliographyCollection
from .conversion.models import ConversionRequest
from .conversion_contexts import GenerationStrategy
from .documents import Document
from .templates.runtime import TemplateRuntime


@dataclass(slots=True)
class ExecutionContext:
    """Resolved execution context for a prepared document conversion."""

    document: Document
    request: ConversionRequest
    template_runtime: TemplateRuntime | None = None
    output_dir: Path | None = None
    template_overrides: dict[str, Any] = field(default_factory=dict)
    slot_requests: dict[str, str] = field(default_factory=dict)
    fragments: list[str] = field(default_factory=list)
    language: str = ""
    bibliography_collection: BibliographyCollection | None = None
    bibliography_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    runtime_common: dict[str, object] = field(default_factory=dict)
    generation: GenerationStrategy = field(default_factory=GenerationStrategy)


__all__ = ["ExecutionContext"]
