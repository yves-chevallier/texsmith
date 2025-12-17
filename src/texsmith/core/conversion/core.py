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
from texsmith.core.bibliography.collection import BibliographyCollection
from texsmith.core.callouts import DEFAULT_CALLOUTS, merge_callouts, normalise_callouts
from texsmith.core.context import DocumentState
from texsmith.core.conversion_contexts import (
    BinderContext,
    DocumentContext,
    GenerationStrategy,
    SegmentContext,
)
from texsmith.core.exceptions import LatexRenderingError, TransformerExecutionError
from texsmith.core.fragments import collect_fragment_partials
from texsmith.core.templates import (
    TemplateBinding,
    TemplateError,
    TemplateRuntime,
    wrap_template_document,
)

from ..diagnostics import DiagnosticEmitter
from .debug import (
    debug_enabled,
    ensure_emitter,
    format_user_friendly_render_error,
    persist_debug_artifacts,
    raise_conversion_error,
    record_event,
)
from .templates import (
    SlotFragment,
    build_binder_context,
    extract_slot_fragments,
)


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
    rule_descriptions: list[dict[str, Any]] = field(default_factory=list)
    assets_map: dict[str, Path] = field(default_factory=dict)


_EMOJI_SPECIAL_MODES = {"artifact", "symbola", "color", "black", "twemoji"}
_CODE_ENGINES = {"minted", "listings", "verbatim", "pygments"}


def _coerce_emoji_mode(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    return lowered if lowered in _EMOJI_SPECIAL_MODES else candidate


def _resolve_code_options(
    binding: TemplateBinding,
    overrides: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return the effective code configuration merging defaults and overrides."""
    default_options: dict[str, Any] = {}
    instance = binding.instance
    if instance is not None:
        try:
            defaults = instance.info.attribute_defaults()
        except Exception:
            defaults = {}
        code_default = defaults.get("code")
        if isinstance(code_default, Mapping):
            default_options.update(code_default)

    merged = dict(default_options)
    override_sources: list[Any] = []
    if overrides:
        if "code" in overrides:
            override_sources.append(overrides.get("code"))
        press_section = overrides.get("press")
        if (
            isinstance(press_section, Mapping)
            and "code" in press_section
            and "code" not in overrides
        ):
            override_sources.append(press_section.get("code"))

    for candidate in override_sources:
        if isinstance(candidate, Mapping):
            merged.update(candidate)
        elif isinstance(candidate, str):
            merged["engine"] = candidate

    engine_value = str(merged.get("engine", "pygments") or "pygments").strip().lower()
    merged["engine"] = engine_value if engine_value in _CODE_ENGINES else "pygments"
    style_value = merged.get("style", "bw")
    if isinstance(style_value, str):
        style_candidate = style_value.strip()
    else:
        style_candidate = str(style_value).strip() if style_value is not None else ""
    merged["style"] = style_candidate or "bw"
    return merged


def _extract_emoji_mode(mapping: Mapping[str, Any] | None) -> str | None:
    if not isinstance(mapping, Mapping):
        return None
    direct = _coerce_emoji_mode(mapping.get("emoji"))
    if direct:
        return direct
    fonts_section = mapping.get("fonts")
    if isinstance(fonts_section, Mapping):
        direct_fonts = _coerce_emoji_mode(fonts_section.get("emoji"))
        if direct_fonts:
            return direct_fonts
    press = mapping.get("press")
    if isinstance(press, Mapping):
        press_direct = _coerce_emoji_mode(press.get("emoji"))
        if press_direct:
            return press_direct
        press_fonts = press.get("fonts")
        if isinstance(press_fonts, Mapping):
            return _coerce_emoji_mode(press_fonts.get("emoji"))
    return None


def _resolve_active_fragments(
    binding: TemplateBinding, overrides: Mapping[str, Any] | None
) -> list[str]:
    """Return the fragment list, respecting explicit overrides when provided."""
    if isinstance(overrides, Mapping) and "fragments" in overrides:
        override_payload = overrides.get("fragments")
        if isinstance(override_payload, list):
            return list(override_payload)
        return []

    runtime = binding.runtime
    if runtime is not None:
        fragments = runtime.extras.get("fragments") if runtime.extras else None
        if isinstance(fragments, list):
            return list(fragments)
    return []


def _resolve_fragment_source_dir(
    overrides: Mapping[str, Any] | None, binder_context: BinderContext
) -> Path | None:
    """Infer the base directory used to resolve fragment paths."""
    candidates = []
    press_section = overrides.get("press") if isinstance(overrides, Mapping) else None
    for container in (overrides, press_section):
        if not isinstance(container, Mapping):
            continue
        for key in ("_source_dir", "source_dir"):
            raw_value = container.get(key)
            if isinstance(raw_value, str) and raw_value.strip():
                candidates.append(Path(raw_value))
    if candidates:
        return candidates[0]
    if getattr(binder_context, "config", None) is not None:
        try:
            return binder_context.config.project_dir
        except Exception:
            return None
    if binder_context.documents:
        try:
            return binder_context.documents[0].source_path.parent
        except Exception:
            return None
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
    diagrams_backend: str | None = None,
    *,
    template_overrides: Mapping[str, Any] | None = None,
    state: DocumentState | None = None,
    template_runtime: TemplateRuntime | None = None,
    wrap_document: bool = True,
    emitter: DiagnosticEmitter | None = None,
    preloaded_bibliography: BibliographyCollection | None = None,
    seen_bibliography_issues: set[tuple[str, str | None, str | None]] | None = None,
) -> ConversionResult:
    """Orchestrate the full HTML-to-LaTeX conversion for a single document."""
    emitter = ensure_emitter(emitter)
    record_event(
        emitter,
        "convert_document",
        {
            "source": str(document.source_path),
            "template": template,
            "language": language,
            "copy_assets": copy_assets,
            "convert_assets": convert_assets,
        },
    )
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
        preloaded_bibliography=preloaded_bibliography,
        seen_bibliography_issues=seen_bibliography_issues,
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
        diagrams_backend=diagrams_backend,
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
    diagrams_backend: str | None,
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

    runtime_common = _build_runtime_common(
        binding=binding,
        binder_context=binder_context,
        document_context=document_context,
        strategy=strategy,
        diagrams_backend=diagrams_backend,
        emitter=emitter,
    )

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

    manual_base_level = document_context.base_level
    drop_title_flag = bool(document_context.drop_title)
    if drop_title_flag and document_context.slot_requests and not binder_context.slot_requests:
        drop_title_flag = False

    fragment_offsets: dict[str, int] = {}
    for fragment in slot_fragments:
        levels = list(getattr(fragment, "heading_levels", []) or [])
        if drop_title_flag and fragment.name == binding.default_slot and levels:
            levels = levels[1:]
        if not levels:
            fragment_offsets[fragment.name] = 0
        else:
            fragment_offsets[fragment.name] = 1 - min(levels)

    segment_registry: dict[str, list[SegmentContext]] = {}
    for fragment in slot_fragments:
        base_value = slot_base_levels.get(fragment.name, effective_base_level)
        fragment_offset = fragment_offsets.get(fragment.name, 0)
        base_offset = manual_base_level + fragment_offset
        segment_registry.setdefault(fragment.name, []).append(
            SegmentContext(
                name=fragment.name,
                html=fragment.html,
                base_level=base_value + base_offset,
                metadata=document_context.front_matter,
                bibliography=binder_context.bibliography_map,
            )
        )

    try:
        render_result = _render_slot_fragments(
            slot_fragments=slot_fragments,
            binding=binding,
            runtime_common=runtime_common,
            slot_base_levels=slot_base_levels,
            fragment_offsets=fragment_offsets,
            manual_base_level=manual_base_level,
            disable_fallback_converters=disable_fallback_converters,
            renderer_kwargs=renderer_kwargs,
            initial_state=initial_state,
            drop_title_flag=drop_title_flag,
            binder_context=binder_context,
            legacy_latex_accents=legacy_latex_accents,
            emitter=emitter,
        )
    except TemplateError as exc:
        if debug_enabled(emitter):
            raise
        raise_conversion_error(emitter, str(exc), exc)
    slot_outputs = render_result["slot_outputs"]
    document_state = render_result["document_state"]
    renderer = render_result["renderer"]

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
    if document_state is not None:
        document_state.requires_shell_escape = (
            document_state.requires_shell_escape or binding.requires_shell_escape
        )
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
                emitter=emitter,
                fragments=list(
                    binder_context.template_overrides.get(
                        "fragments", binding.runtime.extras.get("fragments", [])
                    )
                ),
                template_runtime=binding.runtime,
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

    rule_descriptions: list[dict[str, Any]] = []
    if renderer is not None:
        try:
            rule_descriptions = list(renderer.describe_registered_rules())
        except Exception:
            rule_descriptions = []
    asset_map: dict[str, Path] = {}
    if renderer is not None:
        try:
            asset_map = {str(key): Path(path) for key, path in renderer.assets.items()}
        except Exception:
            asset_map = {}

    return ConversionResult(
        latex_output=latex_output,
        tex_path=tex_path,
        template_engine=binding.engine,
        template_shell_escape=bool(
            binding.requires_shell_escape
            or (document_state and document_state.requires_shell_escape)
        ),
        language=binder_context.language,
        has_bibliography=bool(bibliography_output),
        slot_outputs=dict(slot_outputs),
        default_slot=binding.default_slot,
        document_state=document_state,
        bibliography_path=bibliography_output,
        template_overrides=dict(binder_context.template_overrides),
        document_context=document_context,
        binder_context=binder_context,
        rule_descriptions=rule_descriptions,
        assets_map=asset_map,
    )


def _build_runtime_common(
    *,
    binding: TemplateBinding,
    binder_context: BinderContext,
    document_context: DocumentContext,
    strategy: GenerationStrategy,
    diagrams_backend: str | None,
    emitter: DiagnosticEmitter,
) -> dict[str, object]:
    """Prepare immutable runtime metadata shared across fragment rendering."""
    code_options = _resolve_code_options(binding, binder_context.template_overrides)

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
    template_callouts = binder_context.template_overrides.get("callouts")
    runtime_common["callouts_definitions"] = normalise_callouts(
        merge_callouts(
            DEFAULT_CALLOUTS,
            template_callouts if isinstance(template_callouts, Mapping) else None,
        )
    )
    runtime_common["bibliography"] = binder_context.bibliography_map
    runtime_common["bibliography_collection"] = binder_context.bibliography_collection
    if binding.name is not None:
        runtime_common["template"] = binding.name
    runtime_common["code"] = code_options
    runtime_common["diagrams_backend"] = diagrams_backend or "playwright"
    mermaid_config = binder_context.template_overrides.get("mermaid_config") or (
        binder_context.template_overrides.get("press") or {}
    ).get("mermaid_config")
    if not mermaid_config and binding.runtime and binding.runtime.extras:
        mermaid_config = binding.runtime.extras.get("mermaid_config")
    if mermaid_config:
        runtime_common["mermaid_config"] = mermaid_config
    if strategy.persist_manifest:
        runtime_common["generate_manifest"] = True
    emoji_mode = _extract_emoji_mode(binder_context.template_overrides)
    if not emoji_mode:
        emoji_mode = _extract_emoji_mode(document_context.front_matter)
    if emoji_mode:
        runtime_common["emoji_mode"] = emoji_mode
        binder_context.template_overrides.setdefault("emoji", emoji_mode)
        if emoji_mode != "artifact":
            runtime_common.setdefault("emoji_command", r"\texsmithEmoji")

    return runtime_common


def _render_slot_fragments(
    *,
    slot_fragments: list[SlotFragment],
    binding: TemplateBinding,
    runtime_common: dict[str, object],
    slot_base_levels: Mapping[str, int],
    fragment_offsets: Mapping[str, int],
    manual_base_level: int,
    disable_fallback_converters: bool,
    renderer_kwargs: dict[str, Any],
    initial_state: DocumentState | None,
    drop_title_flag: bool,
    binder_context: BinderContext,
    legacy_latex_accents: bool,
    emitter: DiagnosticEmitter,
) -> dict[str, Any]:
    """Render slot fragments, applying fallback converters when required."""
    formatter = LaTeXFormatter()
    formatter.legacy_latex_accents = legacy_latex_accents
    formatter.default_code_engine = runtime_common.get("code", {}).get(
        "engine", formatter.default_code_engine
    )
    style_override = runtime_common.get("code", {}).get("style", formatter.default_code_style)
    if not isinstance(style_override, str):
        style_override = str(style_override or "")
    formatter.default_code_style = style_override.strip() or formatter.default_code_style
    available_templates = formatter.template_names
    partial_providers: dict[str, str] = dict.fromkeys(available_templates, "core")
    fragment_names = _resolve_active_fragments(binding, binder_context.template_overrides)
    fragment_source_dir = _resolve_fragment_source_dir(
        binder_context.template_overrides, binder_context
    )
    required_partials: dict[str, set[str]] = {}
    if fragment_names:
        fragment_overrides, fragment_required, fragment_providers = collect_fragment_partials(
            fragment_names,
            source_dir=fragment_source_dir,
        )
        for key, override_path in fragment_overrides.items():
            formatter.override_template(key, override_path)
            partial_providers[key] = fragment_providers.get(key, "fragment")
        for key, owners in fragment_required.items():
            required_partials.setdefault(key, set()).update(owners)

    binding.apply_formatter_overrides(formatter)
    template_provider = binding.name or "template"
    for key in binding.formatter_overrides:
        partial_providers[key] = template_provider
    if binding.required_partials:
        for name in binding.required_partials:
            required_partials.setdefault(name, set()).add(template_provider)

    available_partials = set(available_templates)
    missing_partials = [name for name in required_partials if name not in available_partials]
    if missing_partials:
        details = []
        for name in sorted(missing_partials):
            owners = ", ".join(sorted(required_partials.get(name, set()))) or "unknown providers"
            details.append(f"partial '{name}' required by {owners}")
        raise TemplateError(f"Missing {', '.join(details)}.")
    runtime_common["partial_providers"] = partial_providers
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
    for fragment in slot_fragments:
        runtime_fragment = dict(runtime_common)
        base_value = slot_base_levels.get(fragment.name, binding.base_level or 0)
        fragment_offset = fragment_offsets.get(fragment.name, 0)
        base_offset = manual_base_level + fragment_offset
        runtime_fragment["base_level"] = base_value + base_offset
        if fragment.name == "preface":
            runtime_fragment["numbered"] = False
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

    return {
        "slot_outputs": slot_outputs,
        "document_state": document_state,
        "renderer": renderer,
    }


def copy_document_state(target: DocumentState, source: DocumentState) -> None:
    """Synchronise ``target`` with a source ``DocumentState`` instance."""
    for metadata_field in dataclasses.fields(DocumentState):
        setattr(
            target,
            metadata_field.name,
            copy.deepcopy(getattr(source, metadata_field.name)),
        )


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
