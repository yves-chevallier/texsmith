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

from collections.abc import Iterable, Sequence
import copy
from dataclasses import dataclass
from pathlib import Path

from ..domain.conversion.core import ConversionResult, convert_document
from ..domain.conversion.debug import ConversionCallbacks
from ._utils import build_unique_stem_map
from .document import Document


__all__ = [
    "ConversionBundle",
    "LaTeXFragment",
    "RenderSettings",
    "convert_documents",
]


@dataclass(slots=True)
class RenderSettings:
    """Engine-level knobs applied during conversion."""

    parser: str | None = None
    disable_fallback_converters: bool = False
    copy_assets: bool = True
    manifest: bool = False
    persist_debug_html: bool = False
    language: str | None = None
    legacy_latex_accents: bool = False

    def copy(self) -> RenderSettings:
        """Create a deep copy of the settings."""
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
        """Persist the fragment to disk."""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.latex, encoding="utf-8")
        self.output_path = target


@dataclass(slots=True)
class ConversionBundle:
    """Collection returned by :func:`convert_documents`."""

    fragments: list[LaTeXFragment]

    def combined_output(self) -> str:
        """Concatenate all fragments separated by blank lines."""
        return "\n\n".join(fragment.latex for fragment in self.fragments if fragment.latex)


def convert_documents(
    documents: Sequence[Document],
    *,
    output_dir: Path | None = None,
    settings: RenderSettings | None = None,
    callbacks: ConversionCallbacks | None = None,
    bibliography_files: Iterable[Path] | None = None,
) -> ConversionBundle:
    """Convert one or more documents into LaTeX fragments."""
    if not documents:
        raise ValueError("At least one document is required for conversion.")

    settings = settings.copy() if settings is not None else RenderSettings()
    unique_stems = build_unique_stem_map([doc.source_path for doc in documents])

    fragments: list[LaTeXFragment] = []
    for _index, document in enumerate(documents):
        context = document.to_context()
        target_dir = Path(output_dir) if output_dir is not None else Path("build")
        result = convert_document(
            document=context,
            output_dir=target_dir,
            parser=settings.parser,
            disable_fallback_converters=settings.disable_fallback_converters,
            copy_assets=settings.copy_assets,
            manifest=settings.manifest,
            template=None,
            persist_debug_html=settings.persist_debug_html,
            language=settings.language,
            slot_overrides=document.slot_overrides or None,
            bibliography_files=list(bibliography_files or []),
            legacy_latex_accents=settings.legacy_latex_accents,
            callbacks=callbacks,
        )

        stem = unique_stems[document.source_path]
        fragment = LaTeXFragment(
            document=document,
            latex=result.latex_output,
            stem=stem,
            conversion=result,
        )
        if output_dir is not None:
            target = target_dir / f"{stem}.tex"
            fragment.write_to(target)
        fragments.append(fragment)

    return ConversionBundle(fragments=fragments)
