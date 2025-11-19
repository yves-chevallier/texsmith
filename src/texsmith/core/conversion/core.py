"""Core orchestration logic for the conversion pipeline."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import copy
import dataclasses
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any

from texsmith.adapters.docker import is_docker_available
from texsmith.adapters.latex.formatter import LaTeXFormatter
from texsmith.adapters.latex.renderer import LaTeXRenderer
from texsmith.adapters.transformers import has_converter, register_converter
from texsmith.core.context import DocumentState
from texsmith.core.conversion_contexts import (
    BinderContext,
    DocumentContext,
    GenerationStrategy,
    SegmentContext,
)
from texsmith.core.exceptions import LatexRenderingError, TransformerExecutionError
from texsmith.core.templates import (
    TemplateBinding,
    TemplateError,
    TemplateRuntime,
    wrap_template_document,
)

from ..diagnostics import DiagnosticEmitter
from .debug import (
    ConversionError,
    debug_enabled,
    ensure_emitter,
    format_user_friendly_render_error,
    persist_debug_artifacts,
    raise_conversion_error,
)
from .templates import build_binder_context, extract_slot_fragments


@dataclass(slots=True)
class ConversionResult:
    """Artifacts produced during a document conversion."""

    latex_output: str
    tex_path: Path | None
    template_engine: str | None
    template_shell_escape: bool
    language: str
    has_bibliography: bool = False
    slot_outputs: dict[str, str] = field(default_factory=dict)
    default_slot: str = "mainmatter"
    document_state: DocumentState | None = None
    bibliography_path: Path | None = None
    template_overrides: dict[str, Any] = field(default_factory=dict)
    document_context: DocumentContext | None = None
    binder_context: BinderContext | None = None


_EMOJI_MODES = {"artifact", "symbola", "color"}


def _coerce_emoji_mode(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    return candidate if candidate in _EMOJI_MODES else None


def _extract_emoji_mode(mapping: Mapping[str, Any] | None) -> str | None:
    if not isinstance(mapping, Mapping):
        return None
    direct = _coerce_emoji_mode(mapping.get("emoji"))
    if direct:
        return direct
    press = mapping.get("press")
    if isinstance(press, Mapping):
        return _coerce_emoji_mode(press.get("emoji"))
    return None


def convert_document(
    document: DocumentContext,
    output_dir: Path,
    parser: str | None,
    disable_fallback_converters: bool,
    copy_assets: bool,
    convert_assets: bool,
    hash_assets: bool,
    manifest: bool,
    template: str | None,
    persist_debug_html: bool,
    language: str | None,
    slot_overrides: Mapping[str, str] | None,
    bibliography_files: list[Path],
    legacy_latex_accents: bool,
    *,
    template_overrides: Mapping[str, Any] | None = None,
    state: DocumentState | None = None,
    template_runtime: TemplateRuntime | None = None,
    wrap_document: bool = True,
    emitter: DiagnosticEmitter | None = None,
) -> ConversionResult:
    """Orchestrate the full HTML-to-LaTeX conversion for a single document."""
    emitter = ensure_emitter(emitter)
    strategy = GenerationStrategy(
        copy_assets=copy_assets,
        convert_assets=convert_assets,
        hash_assets=hash_assets,
        prefer_inputs=False,
        persist_manifest=manifest,
    )

    output_dir = output_dir.resolve()

    binder_context = build_binder_context(
        document_context=document,
        template=template,
        template_runtime=template_runtime,
        requested_language=language,
        bibliography_files=bibliography_files,
        slot_overrides=slot_overrides,
        output_dir=output_dir,
        strategy=strategy,
        emitter=emitter,
        legacy_latex_accents=legacy_latex_accents,
        session_overrides=template_overrides,
    )

    renderer_kwargs: dict[str, Any] = {
        "output_root": output_dir,
        "copy_assets": strategy.copy_assets,
        "convert_assets": strategy.convert_assets,
        "hash_assets": strategy.hash_assets,
        "parser": parser or "html.parser",
    }

    return _render_document(
        document_context=document,
        binder_context=binder_context,
        renderer_kwargs=renderer_kwargs,
        strategy=strategy,
        disable_fallback_converters=disable_fallback_converters,
        persist_debug_html=persist_debug_html,
        emitter=emitter,
        initial_state=state,
        wrap_document=wrap_document,
        legacy_latex_accents=legacy_latex_accents,
    )


def _render_document(
    *,
    document_context: DocumentContext,
    binder_context: BinderContext,
    renderer_kwargs: dict[str, Any],
    strategy: GenerationStrategy,
    disable_fallback_converters: bool,
    persist_debug_html: bool,
    emitter: DiagnosticEmitter,
    initial_state: DocumentState | None,
    wrap_document: bool,
    legacy_latex_accents: bool,
) -> ConversionResult:
    if persist_debug_html:
        persist_debug_artifacts(
            binder_context.output_dir,
            document_context.source_path,
            document_context.html,
        )

    binding = binder_context.template_binding
    if binding is None:  # pragma: no cover - defensive safeguard
        raise RuntimeError("BinderContext is missing a template binding.")

    effective_base_level = binding.base_level or 0
    slot_base_levels = binding.slot_levels()

    runtime_common: dict[str, object] = {
        "numbered": document_context.numbered,
        "source_dir": document_context.source_path.parent,
        "document_path": document_context.source_path,
        "copy_assets": strategy.copy_assets,
        "convert_assets": strategy.convert_assets,
        "hash_assets": strategy.hash_assets,
        "language": binder_context.language,
        "emitter": emitter,
    }
    if binder_context.bibliography_map:
        runtime_common["bibliography"] = binder_context.bibliography_map
    if binding.name is not None:
        runtime_common["template"] = binding.name
    if strategy.persist_manifest:
        runtime_common["generate_manifest"] = True
    emoji_mode = _extract_emoji_mode(binder_context.template_overrides)
    if not emoji_mode:
        emoji_mode = _extract_emoji_mode(document_context.front_matter)
    if emoji_mode:
        runtime_common["emoji_mode"] = emoji_mode
        if emoji_mode != "artifact":
            runtime_common.setdefault("emoji_command", r"\texsmithEmoji")

    active_slot_requests = binder_context.slot_requests

    parser_backend = str(renderer_kwargs.get("parser", "html.parser"))
    slot_fragments, missing_slots = extract_slot_fragments(
        document_context.html,
        active_slot_requests,
        binding.default_slot,
        slot_definitions=binding.slots,
        parser_backend=parser_backend,
    )
    for message in missing_slots:
        emitter.warning(message)

    segment_registry: dict[str, list[SegmentContext]] = {}
    for fragment in slot_fragments:
        base_value = slot_base_levels.get(fragment.name, effective_base_level)
        segment_registry.setdefault(fragment.name, []).append(
            SegmentContext(
                name=fragment.name,
                html=fragment.html,
                base_level=base_value + document_context.base_level,
                metadata=document_context.front_matter,
                bibliography=binder_context.bibliography_map,
            )
        )

    formatter = LaTeXFormatter()
    formatter.legacy_latex_accents = legacy_latex_accents
    binding.apply_formatter_overrides(formatter)
    renderer: LaTeXRenderer | None = None

    def renderer_factory() -> LaTeXRenderer:
        nonlocal renderer
        if renderer is None:
            renderer = LaTeXRenderer(
                config=binder_context.config,
                formatter=formatter,
                **renderer_kwargs,
            )
        return renderer

    if not disable_fallback_converters:
        ensure_fallback_converters()

    slot_outputs: dict[str, str] = {}
    document_state: DocumentState | None = initial_state
    drop_title_flag = bool(document_context.drop_title)
    base_level_offset = document_context.base_level
    if drop_title_flag and document_context.slot_requests and not binder_context.slot_requests:
        drop_title_flag = False
        base_level_offset += 1
    for fragment in slot_fragments:
        runtime_fragment = dict(runtime_common)
        base_value = slot_base_levels.get(fragment.name, effective_base_level)
        runtime_fragment["base_level"] = (
            base_value + base_level_offset + document_context.heading_level
        )
        if drop_title_flag and fragment.name == binding.default_slot:
            runtime_fragment["drop_title"] = True
            drop_title_flag = False
        fragment_output = ""
        try:
            fragment_output, document_state = render_with_fallback(
                renderer_factory,
                fragment.html,
                runtime_fragment,
                binder_context.bibliography_map,
                state=document_state,
                emitter=emitter,
            )
        except LatexRenderingError as exc:
            if debug_enabled(emitter):
                raise
            message = format_user_friendly_render_error(exc)
            raise_conversion_error(emitter, message, exc)
        existing_fragment = slot_outputs.get(fragment.name, "")
        slot_outputs[fragment.name] = f"{existing_fragment}{fragment_output}"

    if document_state is None:
        document_state = DocumentState(bibliography=dict(binder_context.bibliography_map))

    default_content = slot_outputs.get(binding.default_slot)
    if default_content is None:
        default_content = ""
        slot_outputs[binding.default_slot] = default_content
    latex_output = default_content

    document_context.segments = segment_registry
    for slot_name, segments in segment_registry.items():
        binder_context.bound_segments.setdefault(slot_name, []).extend(segments)

    citations = list(document_state.citations)
    bibliography_output: Path | None = None
    if (
        citations
        and binder_context.bibliography_collection is not None
        and binder_context.bibliography_map
    ):
        try:
            binder_context.output_dir.mkdir(parents=True, exist_ok=True)
            bibliography_output = binder_context.output_dir / "texsmith-bibliography.bib"
            binder_context.bibliography_collection.write_bibtex(
                bibliography_output,
                keys=citations,
            )
        except OSError as exc:
            if debug_enabled(emitter):
                raise
            emitter.warning(f"Failed to write bibliography file: {exc}")
            bibliography_output = None

    tex_path: Path | None = None
    template_instance = binding.instance
    if template_instance is not None and wrap_document:
        try:
            wrap_result = wrap_template_document(
                template=template_instance,
                default_slot=binding.default_slot,
                slot_outputs=slot_outputs,
                document_state=document_state,
                template_overrides=(
                    binder_context.template_overrides if binder_context.template_overrides else None
                ),
                output_dir=binder_context.output_dir,
                copy_assets=strategy.copy_assets,
                output_name=f"{document_context.source_path.stem}.tex",
                bibliography_path=bibliography_output,
            )
            latex_output = wrap_result.latex_output
            tex_path = wrap_result.output_path
        except TemplateError as exc:
            if debug_enabled(emitter):
                raise
            raise_conversion_error(emitter, str(exc), exc)
        except OSError as exc:
            if debug_enabled(emitter):
                raise
            raise_conversion_error(
                emitter,
                f"Failed to write LaTeX output to '{binder_context.output_dir}': {exc}",
                exc,
            )

    return ConversionResult(
        latex_output=latex_output,
        tex_path=tex_path,
        template_engine=binding.engine,
        template_shell_escape=binding.requires_shell_escape,
        language=binder_context.language,
        has_bibliography=bool(citations),
        slot_outputs=dict(slot_outputs),
        default_slot=binding.default_slot,
        document_state=document_state,
        bibliography_path=bibliography_output,
        template_overrides=dict(binder_context.template_overrides),
        document_context=document_context,
        binder_context=binder_context,
    )


def copy_document_state(target: DocumentState, source: DocumentState) -> None:
    """Synchronise ``target`` with a source ``DocumentState`` instance."""
    for metadata_field in dataclasses.fields(DocumentState):
        setattr(target, metadata_field.name, copy.deepcopy(getattr(source, metadata_field.name)))


def render_with_fallback(
    renderer_factory: Callable[[], LaTeXRenderer],
    html: str,
    runtime: dict[str, object],
    bibliography: Mapping[str, dict[str, Any]] | None = None,
    *,
    state: DocumentState | None = None,
    emitter: DiagnosticEmitter | None = None,
) -> tuple[str, DocumentState]:
    """Render HTML to LaTeX, retrying with fallback converters when available."""
    emitter = ensure_emitter(emitter)
    attempts = 0
    bibliography_payload = dict(bibliography or {})
    base_state = state

    while True:
        current_state = (
            copy.deepcopy(base_state)
            if base_state is not None
            else DocumentState(bibliography=dict(bibliography_payload))
        )

        renderer = renderer_factory()
        try:
            output = renderer.render(
                html,
                runtime=runtime,
                state=current_state,
                emitter=emitter,
            )
        except LatexRenderingError as exc:
            attempts += 1
            if attempts >= 5 or not attempt_transformer_fallback(exc):
                raise
            continue

        if base_state is not None:
            copy_document_state(base_state, current_state)
            return output, base_state

        return output, current_state


def attempt_transformer_fallback(error: LatexRenderingError) -> bool:
    """Register placeholder converters when known transformers are unavailable."""
    cause = error.__cause__
    if not isinstance(cause, TransformerExecutionError):
        return False

    message = str(cause).lower()
    applied = False

    if "drawio" in message:
        return False
    if "mermaid" in message:
        return False
    if ("fetch-image" in message or "fetch image" in message) and not has_converter("fetch-image"):
        register_converter("fetch-image", _FallbackConverter("image"))
        applied = True
    return applied


def ensure_fallback_converters() -> None:
    """Install placeholder converters for optional transformer dependencies."""
    if is_docker_available():
        return

    if not has_converter("fetch-image"):
        register_converter("fetch-image", _FallbackConverter("image"))


class _FallbackConverter:
    def __init__(self, name: str):
        self.name = name

    def __call__(self, source: Path | str, *, output_dir: Path, **_: Any) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        original = str(source) if isinstance(source, Path) else source
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()[:12]
        suffix = Path(original).suffix or ".txt"
        filename = f"{self.name}-{digest}.pdf"
        target = output_dir / filename
        target.write_text(
            f"Placeholder PDF for {self.name} ({suffix})",
            encoding="utf-8",
        )
        return target


__all__ = [
    "ConversionResult",
    "attempt_transformer_fallback",
    "convert_document",
    "copy_document_state",
    "ensure_fallback_converters",
    "render_with_fallback",
]
