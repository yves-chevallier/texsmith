"""Conversion helpers that expose a friendly façade over the core engine.

Architecture
: `RenderSettings` stores optional overrides for parser selection, asset
  copying, manifest generation, and diagnostic outputs. A dedicated dataclass
  keeps configuration immutable unless explicitly copied.
: `LaTeXFragment` represents the output of a single document conversion and
  records where it was written on disk, keeping post-processing logic decoupled
  from the rendering pass.
: `ConversionBundle` collects fragments and offers convenience methods like
  `combined_output` for quick previews or testing.
: `convert_documents` bridges `Document` inputs, renders them through the
  conversion engine, and yields the populated bundle.

Implementation Rationale
: Splitting settings, fragments, and bundles into separate dataclasses keeps the
  API explicit. Callers can introspect or extend the workflow without threading
  ad-hoc dictionaries through their code.
: Supporting multiple documents in a single call enables batch rendering and
  powers template sessions. The helper ensures file names are deduplicated and
  optional outputs, such as manifests, remain consistent.

Usage Example
:
    >>> from pathlib import Path
    >>> from tempfile import TemporaryDirectory
    >>> from texsmith.api.document import Document
    >>> from texsmith.api.pipeline import convert_documents
    >>> with TemporaryDirectory() as tmpdir:
    ...     source = Path(tmpdir) / "intro.md"
    ...     _ = source.write_text("# Intro\\nContent")
    ...     output_dir = Path(tmpdir) / "build"
    ...     bundle = convert_documents([Document.from_markdown(source)], output_dir=output_dir)
    ...     (output_dir / "intro.tex").exists()
    True
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.bibliography.collection import BibliographyCollection
from ..core.conversion.core import ConversionResult, convert_document
from ..core.conversion.renderer import TemplateFragment
from ..core.diagnostics import DiagnosticEmitter, NullEmitter
from ._utils import build_unique_stem_map
from .document import Document


if TYPE_CHECKING:  # pragma: no cover - type checking only
    from texsmith.core.context import DocumentState

    from ..core.templates import TemplateRuntime


__all__ = [
    "ConversionBundle",
    "LaTeXFragment",
    "RenderSettings",
    "convert_documents",
    "to_template_fragments",
]


@dataclass(slots=True)
class RenderSettings:
    """Engine-level knobs applied during conversion."""

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

    def copy(self) -> RenderSettings:
        """Create a deep copy of the settings to avoid cross-run mutations."""
        return copy.deepcopy(self)


@dataclass(slots=True)
class LaTeXFragment:
    """Represents a rendered LaTeX fragment."""

    document: Document
    latex: str
    stem: str
    output_path: Path | None = None
    conversion: ConversionResult | None = None

    def write_to(self, target: Path) -> None:
        """Persist the fragment to disk so later template steps can reference it."""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.latex, encoding="utf-8")
        self.output_path = target


@dataclass(slots=True)
class ConversionBundle:
    """Collection returned by :func:`convert_documents`."""

    fragments: list[LaTeXFragment]

    def combined_output(self) -> str:
        """Concatenate all fragments separated by blank lines for quick previews."""
        return "\n\n".join(fragment.latex for fragment in self.fragments if fragment.latex)


def convert_documents(
    documents: Sequence[Document],
    *,
    output_dir: Path | None = None,
    settings: RenderSettings | None = None,
    emitter: DiagnosticEmitter | None = None,
    bibliography_files: Iterable[Path] | None = None,
    template: str | None = None,
    template_runtime: TemplateRuntime | None = None,
    template_overrides: Mapping[str, Any] | None = None,
    wrap_document: bool = True,
    shared_state: DocumentState | None = None,
    write_fragments: bool | None = None,
) -> ConversionBundle:
    """Convert one or more documents into LaTeX fragments while coordinating shared state."""
    if not documents:
        raise ValueError("At least one document is required for conversion.")

    settings = settings.copy() if settings is not None else RenderSettings()
    unique_stems = build_unique_stem_map([doc.source_path for doc in documents])

    shared_bibliography: BibliographyCollection | None = None
    seen_bibliography_issues: set[tuple[str, str | None, str | None]] = set()

    if bibliography_files:
        shared_bibliography = BibliographyCollection()
        shared_bibliography.load_files(bibliography_files)

    fragments: list[LaTeXFragment] = []
    should_write_fragments = write_fragments if write_fragments is not None else True
    state = shared_state
    active_emitter = emitter or NullEmitter()

    for _index, document in enumerate(documents):
        context = document.to_context()
        target_dir = Path(output_dir) if output_dir is not None else Path("build")
        slot_overrides = document.slots.selectors()
        result = convert_document(
            document=context,
            output_dir=target_dir,
            parser=settings.parser,
            disable_fallback_converters=settings.disable_fallback_converters,
            copy_assets=settings.copy_assets,
            convert_assets=settings.convert_assets,
            hash_assets=settings.hash_assets,
            manifest=settings.manifest,
            template=template,
            persist_debug_html=settings.persist_debug_html,
            language=settings.language,
            diagrams_backend=settings.diagrams_backend,
            slot_overrides=slot_overrides or None,
            bibliography_files=list(bibliography_files or []),
            legacy_latex_accents=settings.legacy_latex_accents,
            emitter=active_emitter,
            template_overrides=template_overrides,
            state=None if wrap_document else state,
            template_runtime=template_runtime,
            wrap_document=wrap_document,
            preloaded_bibliography=shared_bibliography,
            seen_bibliography_issues=seen_bibliography_issues,
        )

        if not wrap_document:
            state = result.document_state or state

        stem = unique_stems[document.source_path]
        fragment = LaTeXFragment(
            document=document,
            latex=result.latex_output,
            stem=stem,
            conversion=result,
        )
        if output_dir is not None and should_write_fragments:
            target = target_dir / f"{stem}.tex"
            fragment.write_to(target)
        fragments.append(fragment)

    return ConversionBundle(fragments=fragments)


def to_template_fragments(bundle: ConversionBundle) -> list[TemplateFragment]:
    """Convert API fragments into the core template fragment contract to keep template engines decoupled from API types."""
    fragments: list[TemplateFragment] = []
    for fragment in bundle.fragments:
        conversion = fragment.conversion
        if conversion is None:
            raise ValueError("Template rendering requires conversion metadata for each fragment.")

        document = fragment.document
        slot_includes: set[str] = set()
        if document is not None and hasattr(document, "slots"):
            slot_includes = set(document.slots.includes())

        fragments.append(
            TemplateFragment(
                stem=fragment.stem,
                latex=conversion.latex_output,
                default_slot=conversion.default_slot or "mainmatter",
                slot_outputs=dict(conversion.slot_outputs),
                slot_includes=slot_includes,
                document_state=conversion.document_state,
                bibliography_path=conversion.bibliography_path,
                template_engine=conversion.template_engine,
                requires_shell_escape=conversion.template_shell_escape,
                template_overrides=dict(conversion.template_overrides),
                output_path=fragment.output_path,
                front_matter=document.front_matter,
                source_path=document.source_path,
                rule_descriptions=list(conversion.rule_descriptions),
                assets=dict(conversion.assets_map),
            )
        )
    return fragments
