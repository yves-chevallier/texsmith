"""Conversion orchestration utilities for CLI and embedding integrations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import copy
from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

import yaml

from texsmith.core.exceptions import ConversionError
from texsmith.core.sources import is_bibliography, is_front_matter, is_markdown
from texsmith.diagnostics import DiagnosticEmitter, ensure_emitter

from ..documents import Document, TitleStrategy, front_matter_has_title
from ..front_matter import split_front_matter
from ..templates.runtime import declared_containers
from ..templates.session import TemplateRenderResult, TemplateSession, get_template
from .core import ConversionBundle, convert_documents
from .inputs import (
    UnsupportedInputError,
    extract_front_matter_slots,
)
from .models import ConversionRequest


__all__ = [
    "ConversionResponse",
    "ConversionService",
    "SplitInputsResult",
    "validate_input_source",
]


@dataclass(slots=True)
class SplitInputsResult:
    """Structured partitioning of input paths."""

    documents: list[Path]
    bibliography_files: list[Path]
    front_matter: Mapping[str, Any] | None = None
    front_matter_paths: list[Path] = field(default_factory=list)


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
        """Return True when the response contains template output rather than raw fragments."""
        return isinstance(self.result, TemplateRenderResult)

    @property
    def bundle(self) -> ConversionBundle:
        """Expose the conversion bundle while guarding against template misuse."""
        if isinstance(self.result, ConversionBundle):
            return self.result
        raise TypeError("ConversionResponse does not contain a ConversionBundle.")

    @property
    def render_result(self) -> TemplateRenderResult:
        """Expose the template render result while guarding against bundle misuse."""
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
    ) -> SplitInputsResult:
        """Separate document inputs, bibliography files, and optional front matter to keep downstream parsing deterministic."""
        inline_bibliography: list[Path] = []
        documents: list[Path] = []
        front_matter_entries: list[tuple[Path, Mapping[str, Any]]] = []

        for candidate in inputs:
            if is_bibliography(candidate):
                inline_bibliography.append(candidate)
                continue
            loaded_front_matter = _load_front_matter_file(candidate)
            if isinstance(loaded_front_matter, Mapping):
                front_matter_entries.append((candidate, loaded_front_matter))
                continue
            documents.append(candidate)

        bibliography_paths = _deduplicate_paths([*inline_bibliography, *extra_bibliography])
        if not documents and front_matter_entries:
            # Treat the last front-matter file as an input document so templates can
            # operate on YAML sources without requiring additional Markdown/HTML
            # content; any earlier YAML inputs keep acting as shared configuration.
            last_path, _ = front_matter_entries.pop()
            documents.append(last_path)

        front_matter: Mapping[str, Any] | None = None
        front_matter_paths: list[Path] = []
        for path, payload in front_matter_entries:
            # Deep-merge in argument order: later files override earlier ones.
            front_matter = _merge_front_matter(front_matter or {}, payload)
            front_matter_paths.append(path)

        return SplitInputsResult(
            documents=documents,
            bibliography_files=bibliography_paths,
            front_matter=front_matter,
            front_matter_paths=front_matter_paths,
        )

    def prepare_documents(self, request: ConversionRequest) -> _PreparedBatch:
        """Normalise input sources into :class:`Document` instances so conversion steps operate on consistent objects."""
        emitter = ensure_emitter(request.emitter)
        # Before the first parse: the containers the template's passes read are
        # known constructs for this run, and tmark decides that while it parses.
        emitter.sink.declare_containers(declared_containers(request.template))
        documents: list[Document] = []
        mapping: dict[Path, Document] = {}
        shared_front_matter = _normalise_front_matter(request.front_matter)

        for index, path in enumerate(request.documents):
            validate_input_source(path)
            extract_title = request.promote_title and index == 0 and not request.suppress_title
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

            document = Document.from_markdown(
                path,
                base_level=request.base_level,
                promote_title=extract_title,
                strip_heading=effective_strip,
                suppress_title=request.suppress_title,
                title_strategy=strategy,
                numbered=request.numbered,
                emitter=emitter,
            )

            documents.append(document)
            mapping[path] = document

        press_sources = _collect_press_sources(documents, shared_front_matter, request)
        if len(press_sources) > 1:
            raise ConversionError(
                "Multiple sources declare press metadata; only one is allowed for a conversion: "
                + ", ".join(press_sources)
            )

        _apply_shared_front_matter(documents, shared_front_matter)

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
        """Execute a conversion workflow and return a structured response, routing to template or raw conversion paths as needed."""
        batch = prepared or self.prepare_documents(request)
        settings = request.replace()
        emitter = batch.emitter

        if request.template is None:
            bundle = convert_documents(
                batch.documents,
                output_dir=request.render_dir,
                settings=settings,
                emitter=emitter,
                bibliography_files=batch.bibliography_files,
            )
            if request.render_dir is not None and batch.documents:
                _publish_reference_inventory(
                    batch.documents,
                    output_dir=Path(request.render_dir),
                    stem=batch.documents[0].source_path.stem,
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
        render_result = session.render(target_dir, embed_documents=request.embed_documents)
        _publish_reference_inventory(
            batch.documents,
            output_dir=render_result.main_tex_path.parent,
            stem=render_result.main_tex_path.stem,
        )
        return ConversionResponse(
            request=request,
            documents=batch.documents,
            bibliography_files=batch.bibliography_files,
            result=render_result,
            emitter=emitter,
        )

    @staticmethod
    def _initialise_template_session(
        template: str,
        *,
        settings: ConversionRequest,
        emitter: DiagnosticEmitter,
    ) -> TemplateSession:
        return get_template(
            template,
            settings=settings,
            emitter=emitter,
        )


logger = logging.getLogger(__name__)


def _publish_reference_inventory(
    documents: Sequence[Document],
    *,
    output_dir: Path,
    stem: str,
) -> None:
    """Publish the ``*.refs.json`` other documents cite this one through."""
    from texsmith.core.crossrefs import anchors_from_resolved, publish_inventory

    primary = documents[0] if documents else None
    if primary is None:
        return
    metadata = dict(primary.front_matter)
    if not metadata.get("title") and primary.extracted_title:
        metadata["title"] = primary.extracted_title
    # One inventory per build: the anchors of every document of the batch, in
    # conversion order, since they share one continuous counter series.
    anchors = {}
    for document in documents:
        anchors.update(anchors_from_resolved(document.resolved))
    try:
        publish_inventory(
            output_dir=output_dir,
            stem=stem,
            metadata=metadata,
            source_path=primary.source_path,
            anchors=anchors,
        )
    except OSError as exc:  # pragma: no cover - the conversion itself succeeded
        logger.warning("Could not write the cross-reference inventory: %s", exc)


_NOT_FRONT_MATTER = object()


def _load_front_matter_file(path: Path) -> Mapping[str, Any] | object:
    """Return parsed front matter when the path looks like a metadata file."""
    suffix = path.suffix.lower()
    if suffix not in {".yml", ".yaml"}:
        return _NOT_FRONT_MATTER
    name_lower = path.name.lower()
    if name_lower in {"mkdocs.yml", "mkdocs.yaml"}:
        return _NOT_FRONT_MATTER
    try:
        payload = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConversionError(f"Failed to read front matter source '{path}': {exc}") from exc

    if not payload.strip():
        return {}

    if payload.lstrip().startswith("---"):
        metadata, body = split_front_matter(payload)
        if body.strip():
            return _NOT_FRONT_MATTER
        return metadata

    try:
        parsed = yaml.safe_load(payload)
    except yaml.YAMLError as exc:
        raise ConversionError(f"Invalid YAML front matter in '{path}': {exc}") from exc
    return dict(parsed) if isinstance(parsed, Mapping) else _NOT_FRONT_MATTER


def _normalise_front_matter(data: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if data is None:
        return None
    if not isinstance(data, Mapping):
        raise ConversionError("Front matter must be a mapping when provided programmatically.")
    return copy.deepcopy(dict(data))


def _front_matter_declares_press(metadata: Mapping[str, Any] | None) -> bool:
    if not isinstance(metadata, Mapping):
        return False
    press_section = metadata.get("press")
    if isinstance(press_section, Mapping):
        return True
    return any(isinstance(key, str) and key.startswith("press.") for key in metadata)


def _merge_front_matter(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = copy.deepcopy(dict(base))
    for key, value in override.items():
        if key in merged and isinstance(merged[key], Mapping) and isinstance(value, Mapping):
            merged[key] = _merge_front_matter(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _apply_shared_front_matter(
    documents: list[Document],
    shared_front_matter: Mapping[str, Any] | None,
) -> None:
    if not shared_front_matter:
        return
    for document in documents:
        merged = _merge_front_matter(shared_front_matter, document.front_matter)
        document.set_front_matter(merged)
        if document.title_strategy is TitleStrategy.PROMOTE_METADATA and front_matter_has_title(
            merged
        ):
            document.title_strategy = TitleStrategy.KEEP
        base_mapping, _base_options = extract_front_matter_slots(merged)
        document.reset_slots(base_mapping)


def _collect_press_sources(
    documents: list[Document],
    shared_front_matter: Mapping[str, Any] | None,
    request: ConversionRequest,
) -> list[str]:
    sources: list[str] = []
    if shared_front_matter and _front_matter_declares_press(shared_front_matter):
        # Merged configuration files count as a single press source; conflicts
        # between them are already resolved by the merge (later files win).
        if request.front_matter_paths:
            sources.append(", ".join(str(path) for path in request.front_matter_paths))
        else:
            sources.append("front matter")
    for document in documents:
        if _front_matter_declares_press(document.front_matter):
            sources.append(str(document.source_path))
    return sources


def validate_input_source(path: Path) -> None:
    """Reject an input whose suffix names something TeXSmith does not read."""
    if is_markdown(path):
        return
    if is_front_matter(path):
        if path.name.lower() in {"mkdocs.yml", "mkdocs.yaml"}:
            raise UnsupportedInputError("MkDocs configuration files are not supported.")
        return
    raise UnsupportedInputError(
        f"Unsupported input file type '{path.suffix.lower() or '<none>'}'. "
        "Provide a Markdown source (.md)."
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
