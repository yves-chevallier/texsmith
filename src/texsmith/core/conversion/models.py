"""SSOT model for conversion settings and requests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from ..diagnostics import DiagnosticEmitter


@dataclass(slots=True)
class SlotAssignment:
    """Directive mapping a document onto a template slot."""

    slot: str
    selector: str | None
    include_document: bool


@dataclass(slots=True)
class ConversionRequest:
    """Immutable description of conversion inputs and engine settings."""

    documents: Sequence[Path] = field(default_factory=tuple)
    bibliography_files: Sequence[Path] = field(default_factory=list)
    front_matter: Mapping[str, Any] | None = None
    front_matter_path: Path | None = None
    slot_assignments: Mapping[Path, Sequence[SlotAssignment]] = field(default_factory=dict)

    selector: str = "article.md-content__inner"
    full_document: bool = False
    base_level: int = 0
    strip_heading_all: bool = False
    strip_heading_first_document: bool = False
    promote_title: bool = True
    suppress_title: bool = False
    numbered: bool = True
    markdown_extensions: Sequence[str] = field(default_factory=list)

    template: str | None = None
    render_dir: Path | None = None
    template_options: Mapping[str, Any] = field(default_factory=dict)
    embed_fragments: bool = False
    enable_fragments: Sequence[str] = field(default_factory=tuple)
    disable_fragments: Sequence[str] = field(default_factory=tuple)

    parser: str | None = None
    disable_fallback_converters: bool = False
    copy_assets: bool = True
    convert_assets: bool = False
    hash_assets: bool = False
    manifest: bool = False
    persist_debug_html: bool = False
    language: str | None = None
    legacy_latex_accents: bool = False
    diagrams_backend: str | None = None

    emitter: DiagnosticEmitter | None = None

    def copy(self) -> ConversionRequest:
        """Create a deep copy to avoid cross-run mutations."""
        payload: dict[str, Any] = {}
        for definition in fields(self):
            value = getattr(self, definition.name)
            if definition.name == "emitter":
                payload[definition.name] = value
            else:
                payload[definition.name] = copy.deepcopy(value)
        return ConversionRequest(**payload)
