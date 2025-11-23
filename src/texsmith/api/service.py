"""Conversion orchestration utilities for CLI and embedding integrations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from texsmith.core.conversion.debug import ensure_emitter
from texsmith.core.conversion.inputs import InputKind, UnsupportedInputError
from texsmith.core.diagnostics import DiagnosticEmitter

from .document import Document, TitleStrategy
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
    base_level: int = 0
    strip_heading_all: bool = False
    strip_heading_first_document: bool = False
    promote_title: bool = True
    suppress_title: bool = False
    numbered: bool = True
    markdown_extensions: Sequence[str] = field(default_factory=list)

    parser: str | None = None
    disable_fallback_converters: bool = False
    copy_assets: bool = True
    convert_assets: bool = False
    hash_assets: bool = False
    manifest: bool = False
    persist_debug_html: bool = False
    language: str | None = None
    legacy_latex_accents: bool = False

    template: str | None = None
    render_dir: Path | None = None
    template_options: Mapping[str, Any] = field(default_factory=dict)

    emitter: DiagnosticEmitter | None = None


@dataclass(slots=True)
class ConversionResponse:
    """Captured outcome of :class:`ConversionService` execution."""

    request: ConversionRequest
    documents: list[Document]
    bibliography_files: list[Path]
    result: ConversionBundle | TemplateRenderResult
    emitter: DiagnosticEmitter | None = None

    @property
    def is_template(self) -> bool:
        return isinstance(self.result, TemplateRenderResult)

    @property
    def bundle(self) -> ConversionBundle:
        if isinstance(self.result, ConversionBundle):
            return self.result
        raise TypeError("ConversionResponse does not contain a ConversionBundle.")

    @property
    def render_result(self) -> TemplateRenderResult:
        if isinstance(self.result, TemplateRenderResult):
            return self.result
        raise TypeError("ConversionResponse does not contain a TemplateRenderResult.")


@dataclass(slots=True)
class _PreparedBatch:
    documents: list[Document]
    document_map: dict[Path, Document]
    emitter: DiagnosticEmitter
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
        emitter = ensure_emitter(request.emitter)
        documents: list[Document] = []
        mapping: dict[Path, Document] = {}

        for index, path in enumerate(request.documents):
            input_kind = classify_input_source(path)
            extract_title = (
                request.promote_title
                and request.template is not None
                and index == 0
                and not request.suppress_title
            )
            effective_strip = request.strip_heading_all or (
                request.strip_heading_first_document and index == 0
            )
            strategy: TitleStrategy | None = None
            if effective_strip:
                strategy = TitleStrategy.DROP
                extract_title = False
            elif not extract_title:
                strategy = TitleStrategy.KEEP
            else:
                strategy = None

            if input_kind is InputKind.MARKDOWN:
                document = Document.from_markdown(
                    path,
                    extensions=list(request.markdown_extensions),
                    base_level=request.base_level,
                    promote_title=extract_title,
                    strip_heading=effective_strip,
                    suppress_title=request.suppress_title,
                    title_strategy=strategy,
                    numbered=request.numbered,
                    emitter=emitter,
                )
            else:
                document = Document.from_html(
                    path,
                    selector=request.selector,
                    base_level=request.base_level,
                    promote_title=extract_title,
                    strip_heading=effective_strip,
                    suppress_title=request.suppress_title,
                    title_strategy=strategy,
                    numbered=request.numbered,
                    full_document=request.full_document,
                    emitter=emitter,
                )

            documents.append(document)
            mapping[path] = document

        for path, directives in request.slot_assignments.items():
            document = mapping.get(path)
            if document is None or not directives:
                continue
            for directive in directives:
                document.assign_slot(
                    directive.slot,
                    selector=directive.selector,
                    include_document=directive.include_document,
                )
        bibliography = _deduplicate_paths(request.bibliography_files)
        return _PreparedBatch(
            documents=documents,
            document_map=mapping,
            emitter=emitter,
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
        emitter = batch.emitter

        if request.template is None:
            bundle = convert_documents(
                batch.documents,
                output_dir=request.render_dir,
                settings=settings,
                emitter=emitter,
                bibliography_files=batch.bibliography_files,
            )
            return ConversionResponse(
                request=request,
                documents=batch.documents,
                bibliography_files=batch.bibliography_files,
                result=bundle,
                emitter=emitter,
            )

        session = self._initialise_template_session(
            request.template,
            settings=settings,
            emitter=emitter,
        )
        if request.template_options:
            session.update_options(request.template_options)
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
            result=render_result,
            emitter=emitter,
        )

    @staticmethod
    def _build_render_settings(request: ConversionRequest) -> RenderSettings:
        return RenderSettings(
            parser=request.parser,
            disable_fallback_converters=request.disable_fallback_converters,
            copy_assets=request.copy_assets,
            convert_assets=request.convert_assets,
            hash_assets=request.hash_assets,
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
        emitter: DiagnosticEmitter,
    ) -> TemplateSession:
        return get_template(
            template,
            settings=settings,
            emitter=emitter,
        )


def classify_input_source(path: Path) -> InputKind:
    """Determine the document kind based on filename suffix."""
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return InputKind.MARKDOWN
    if suffix in {".yaml", ".yml"}:
        if path.name.lower() in {"mkdocs.yml", "mkdocs.yaml"}:
            raise UnsupportedInputError("MkDocs configuration files are not supported.")
        return InputKind.MARKDOWN
    if suffix in {".html", ".htm"}:
        return InputKind.HTML
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
