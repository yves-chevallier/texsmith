"""Conversion orchestration utilities for CLI and embedding integrations."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from texsmith.core.conversion.debug import ConversionCallbacks
from texsmith.core.conversion.inputs import InputKind, UnsupportedInputError

from .document import Document
from .pipeline import ConversionBundle, RenderSettings, convert_documents
from .templates import TemplateRenderResult, TemplateSession, get_template


__all__ = [
    "ConversionRequest",
    "ConversionResponse",
    "ConversionService",
    "SlotAssignment",
    "classify_input_source",
]


@dataclass(slots=True)
class SlotAssignment:
    """Directive mapping a document onto a template slot."""

    slot: str
    selector: str | None
    include_document: bool


@dataclass(slots=True)
class ConversionRequest:
    """Immutable description of a conversion run."""

    documents: Sequence[Path]
    bibliography_files: Sequence[Path] = field(default_factory=list)
    slot_assignments: Mapping[Path, Sequence[SlotAssignment]] = field(default_factory=dict)

    selector: str = "article.md-content__inner"
    full_document: bool = False
    heading_level: int = 0
    base_level: int = 0
    drop_title_all: bool = False
    drop_title_first_document: bool = False
    numbered: bool = True
    markdown_extensions: Sequence[str] = field(default_factory=list)

    parser: str | None = None
    disable_fallback_converters: bool = False
    copy_assets: bool = True
    manifest: bool = False
    persist_debug_html: bool = False
    language: str | None = None
    legacy_latex_accents: bool = False

    template: str | None = None
    render_dir: Path | None = None

    emit_warning: Callable[[str, Exception | None], None] | None = None
    emit_error: Callable[[str, Exception | None], None] | None = None
    record_event: Callable[[str, Mapping[str, Any]], None] | None = None
    debug_enabled: bool = False


@dataclass(slots=True)
class ConversionResponse:
    """Captured outcome of :class:`ConversionService` execution."""

    request: ConversionRequest
    documents: list[Document]
    bibliography_files: list[Path]
    bundle: ConversionBundle | None = None
    render_result: TemplateRenderResult | None = None
    callbacks: ConversionCallbacks | None = None

    @property
    def uses_template(self) -> bool:
        """Return True when a template workflow produced the response."""
        return self.render_result is not None


@dataclass(slots=True)
class _PreparedBatch:
    documents: list[Document]
    document_map: dict[Path, Document]
    callbacks: ConversionCallbacks
    bibliography_files: list[Path]


class ConversionService:
    """High-level façade that encapsulates document preparation and execution."""

    def split_inputs(
        self,
        inputs: Iterable[Path],
        extra_bibliography: Iterable[Path] = (),
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

    def prepare_documents(self, request: ConversionRequest) -> _PreparedBatch:
        """Normalise input sources into :class:`Document` instances."""
        callbacks = self._build_callbacks(request)
        documents: list[Document] = []
        mapping: dict[Path, Document] = {}

        for index, path in enumerate(request.documents):
            input_kind = classify_input_source(path)
            effective_drop = request.drop_title_all or (
                request.drop_title_first_document and index == 0
            )

            if input_kind is InputKind.MARKDOWN:
                document = Document.from_markdown(
                    path,
                    extensions=list(request.markdown_extensions),
                    heading=request.heading_level,
                    base_level=request.base_level,
                    drop_title=effective_drop,
                    numbered=request.numbered,
                    callbacks=callbacks,
                )
            else:
                document = Document.from_html(
                    path,
                    selector=request.selector,
                    heading=request.heading_level,
                    base_level=request.base_level,
                    drop_title=effective_drop,
                    numbered=request.numbered,
                    full_document=request.full_document,
                    callbacks=callbacks,
                )

            documents.append(document)
            mapping[path] = document

        self._apply_slot_assignments(mapping, request.slot_assignments)
        bibliography = _deduplicate_paths(request.bibliography_files)
        return _PreparedBatch(
            documents=documents,
            document_map=mapping,
            callbacks=callbacks,
            bibliography_files=bibliography,
        )

    def execute(
        self,
        request: ConversionRequest,
        *,
        prepared: _PreparedBatch | None = None,
    ) -> ConversionResponse:
        """Execute a conversion workflow and return a structured response."""
        batch = prepared or self.prepare_documents(request)
        settings = self._build_render_settings(request)

        if request.template is None:
            bundle = convert_documents(
                batch.documents,
                output_dir=request.render_dir,
                settings=settings,
                callbacks=batch.callbacks,
                bibliography_files=batch.bibliography_files,
            )
            return ConversionResponse(
                request=request,
                documents=batch.documents,
                bibliography_files=batch.bibliography_files,
                bundle=bundle,
                callbacks=batch.callbacks,
            )

        session = self._initialise_template_session(
            request.template,
            settings=settings,
            callbacks=batch.callbacks,
        )
        if batch.bibliography_files:
            session.add_bibliography(*batch.bibliography_files)
        for document in batch.documents:
            session.add_document(document)

        target_dir = (request.render_dir or Path("build")).resolve()
        render_result = session.render(target_dir)
        return ConversionResponse(
            request=request,
            documents=batch.documents,
            bibliography_files=batch.bibliography_files,
            render_result=render_result,
            callbacks=batch.callbacks,
        )

    @staticmethod
    def _apply_slot_assignments(
        document_map: Mapping[Path, Document],
        assignments: Mapping[Path, Sequence[SlotAssignment]],
    ) -> None:
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

    @staticmethod
    def _build_callbacks(request: ConversionRequest) -> ConversionCallbacks:
        return ConversionCallbacks(
            emit_warning=request.emit_warning,
            emit_error=request.emit_error,
            debug_enabled=request.debug_enabled,
            record_event=request.record_event,
        )

    @staticmethod
    def _build_render_settings(request: ConversionRequest) -> RenderSettings:
        return RenderSettings(
            parser=request.parser,
            disable_fallback_converters=request.disable_fallback_converters,
            copy_assets=request.copy_assets,
            manifest=request.manifest,
            persist_debug_html=request.persist_debug_html,
            language=request.language,
            legacy_latex_accents=request.legacy_latex_accents,
        )

    @staticmethod
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


def _deduplicate_paths(values: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in values:
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result
