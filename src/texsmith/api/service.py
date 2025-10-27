"""High-level conversion orchestration helpers shared across front ends."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..conversion.debug import ConversionCallbacks
from ..conversion.inputs import InputKind, UnsupportedInputError
from .document import Document
from .pipeline import ConversionBundle, RenderSettings, convert_documents
from .templates import TemplateRenderResult, TemplateSession, get_template


@dataclass(slots=True)
class SlotAssignment:
    """Directive mapping a document onto a template slot."""

    slot: str
    selector: str | None
    include_document: bool


@dataclass(slots=True)
class DocumentPreparationResult:
    """Prepared documents ready to be rendered."""

    documents: list[Document]
    document_map: dict[Path, Document]


@dataclass(slots=True)
class ConversionOutcome:
    """Outcome produced by :func:`execute_conversion`."""

    bundle: ConversionBundle | None = None
    render_result: TemplateRenderResult | None = None

    @property
    def uses_template(self) -> bool:
        return self.render_result is not None


def split_document_inputs(
    inputs: Iterable[Path],
    extra_bibliography: Iterable[Path],
) -> tuple[list[Path], list[Path]]:
    """Separate document inputs from bibliography files."""
    inline_bibliography: list[Path] = []
    documents: list[Path] = []

    for candidate in inputs:
        suffix = candidate.suffix.lower()
        if suffix in {".bib", ".bibtex"}:
            inline_bibliography.append(candidate)
            continue
        documents.append(candidate)

    bibliography_paths = _deduplicate_paths([*inline_bibliography, *extra_bibliography])
    return documents, bibliography_paths


def build_callbacks(
    *,
    emit_warning: Callable[[str, Exception | None], None] | None,
    emit_error: Callable[[str, Exception | None], None] | None,
    debug_enabled: bool,
) -> ConversionCallbacks:
    """Construct :class:`ConversionCallbacks` from callables."""
    return ConversionCallbacks(
        emit_warning=emit_warning,
        emit_error=emit_error,
        debug_enabled=debug_enabled,
    )


def build_render_settings(
    *,
    parser: str | None,
    disable_fallback_converters: bool,
    copy_assets: bool,
    manifest: bool,
    persist_debug_html: bool,
    language: str | None,
    legacy_latex_accents: bool,
) -> RenderSettings:
    """Create a :class:`RenderSettings` instance from primitive values."""
    return RenderSettings(
        parser=parser,
        disable_fallback_converters=disable_fallback_converters,
        copy_assets=copy_assets,
        manifest=manifest,
        persist_debug_html=persist_debug_html,
        language=language,
        legacy_latex_accents=legacy_latex_accents,
    )


def prepare_documents(
    paths: Sequence[Path],
    *,
    selector: str,
    full_document: bool,
    heading_level: int,
    base_level: int,
    drop_title_all: bool,
    drop_title_first_document: bool,
    numbered: bool,
    markdown_extensions: Sequence[str],
    callbacks: ConversionCallbacks | None,
) -> DocumentPreparationResult:
    """Normalise input sources into :class:`Document` instances."""
    documents: list[Document] = []
    mapping: dict[Path, Document] = {}

    for index, path in enumerate(paths):
        input_kind = classify_input_source(path)
        effective_drop = drop_title_all or (drop_title_first_document and index == 0)

        if input_kind is InputKind.MARKDOWN:
            document = Document.from_markdown(
                path,
                extensions=list(markdown_extensions),
                heading=heading_level,
                base_level=base_level,
                drop_title=effective_drop,
                numbered=numbered,
                callbacks=callbacks,
            )
        else:
            document = Document.from_html(
                path,
                selector=selector,
                heading=heading_level,
                base_level=base_level,
                drop_title=effective_drop,
                numbered=numbered,
                full_document=full_document,
                callbacks=callbacks,
            )

        documents.append(document)
        mapping[path] = document

    return DocumentPreparationResult(documents=documents, document_map=mapping)


def apply_slot_assignments(
    document_map: Mapping[Path, Document],
    assignments: Mapping[Path, Sequence[SlotAssignment]],
) -> None:
    """Apply slot directives to prepared documents."""
    for path, directives in assignments.items():
        document = document_map.get(path)
        if document is None or not directives:
            continue
        for directive in directives:
            if directive.selector is not None:
                document.assign_slot(
                    directive.slot,
                    selector=directive.selector,
                    include_document=directive.include_document,
                )
            else:
                document.assign_slot(
                    directive.slot,
                    include_document=True,
                )


def execute_conversion(
    documents: Sequence[Document],
    *,
    settings: RenderSettings,
    callbacks: ConversionCallbacks | None,
    bibliography_files: Iterable[Path],
    template: str | None = None,
    render_dir: Path | None = None,
) -> ConversionOutcome:
    """Run the conversion pipeline with optional template rendering."""
    if template is None:
        bundle = convert_documents(
            documents,
            output_dir=render_dir,
            settings=settings,
            callbacks=callbacks,
            bibliography_files=list(bibliography_files),
        )
        return ConversionOutcome(bundle=bundle)

    session = _initialise_template_session(
        template,
        settings=settings,
        callbacks=callbacks,
    )

    if bibliography_files:
        session.add_bibliography(*bibliography_files)

    for document in documents:
        session.add_document(document)

    target_dir = (render_dir or Path("build")).resolve()
    render_result = session.render(target_dir)
    return ConversionOutcome(render_result=render_result)


def classify_input_source(path: Path) -> InputKind:
    """Determine the document kind based on filename suffix."""
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return InputKind.MARKDOWN
    if suffix in {".html", ".htm"}:
        return InputKind.HTML
    if suffix in {".yaml", ".yml"}:
        raise UnsupportedInputError(
            "MkDocs configuration files are not supported as input. "
            "Provide a Markdown source or an HTML document."
        )
    raise UnsupportedInputError(
        f"Unsupported input file type '{suffix or '<none>'}'. "
        "Provide a Markdown source (.md) or HTML document (.html)."
    )


def _initialise_template_session(
    template: str,
    *,
    settings: RenderSettings,
    callbacks: ConversionCallbacks | None,
) -> TemplateSession:
    return get_template(
        template,
        settings=settings,
        callbacks=callbacks,
    )


def _deduplicate_paths(values: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in values:
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


__all__ = [
    "ConversionOutcome",
    "DocumentPreparationResult",
    "SlotAssignment",
    "apply_slot_assignments",
    "build_callbacks",
    "build_render_settings",
    "classify_input_source",
    "execute_conversion",
    "prepare_documents",
    "split_document_inputs",
]
