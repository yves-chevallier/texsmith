"""High-level conversion helpers built on top of the core engine."""

from __future__ import annotations

from dataclasses import dataclass, field
import copy
from pathlib import Path
from typing import Iterable, List, Sequence

from ..conversion import (
    ConversionCallbacks,
    ConversionResult,
    convert_document,
)
from ..templates import LATEX_HEADING_LEVELS
from .document import Document
from ._utils import build_unique_stem_map


__all__ = [
    "RenderSettings",
    "LaTeXFragment",
    "ConversionBundle",
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

    def copy(self) -> "RenderSettings":
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

    fragments: List[LaTeXFragment]

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
    for index, document in enumerate(documents):
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
