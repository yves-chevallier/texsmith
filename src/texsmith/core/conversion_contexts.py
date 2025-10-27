"""Context objects used during document conversion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .bibliography import BibliographyCollection
from .config import BookConfig
from .templates import TemplateBinding


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
class DocumentContext:
    """Document-level context produced before rendering."""

    name: str
    source_path: Path
    html: str
    base_level: int
    heading_level: int
    numbered: bool
    drop_title: bool
    front_matter: dict[str, Any] = field(default_factory=dict)
    slot_requests: dict[str, str] = field(default_factory=dict)
    language: str | None = None
    bibliography: dict[str, Any] = field(default_factory=dict)
    assets: list[AssetMapping] = field(default_factory=list)
    segments: dict[str, list[SegmentContext]] = field(default_factory=dict)


@dataclass(slots=True)
class BinderContext:
    """Binder-level context describing template binding and global state."""

    output_dir: Path
    config: BookConfig
    strategy: GenerationStrategy
    language: str
    slot_requests: dict[str, str]
    template_overrides: dict[str, Any]
    bibliography_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    bibliography_collection: BibliographyCollection | None = None
    template_binding: TemplateBinding | None = None
    documents: list[DocumentContext] = field(default_factory=list)
    bound_segments: dict[str, list[SegmentContext]] = field(default_factory=dict)


__all__ = [
    "AssetMapping",
    "BinderContext",
    "DocumentContext",
    "GenerationStrategy",
    "SegmentContext",
]
