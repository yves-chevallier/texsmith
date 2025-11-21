"""Shared helpers for wrapping LaTeX bodies with template metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from texsmith.core.callouts import DEFAULT_CALLOUTS, merge_callouts, normalise_callouts
from texsmith.core.fragments import render_fragments
from texsmith.core.templates import TemplateRuntime

from texsmith.core.conversion.debug import ensure_emitter, record_event
from texsmith.core.diagnostics import DiagnosticEmitter
from texsmith.fonts.analyzer import analyse_font_requirements

from ..context import DocumentState
from .base import WrappableTemplate
from .loader import copy_template_assets


@dataclass(slots=True)
class TemplateWrapResult:
    """Result artefacts produced after wrapping LaTeX with a template."""

    latex_output: str
    template_context: dict[str, Any]
    output_path: Path | None
    asset_paths: list[Path] = field(default_factory=list)


def wrap_template_document(
    *,
    template: WrappableTemplate,
    default_slot: str,
    slot_outputs: Mapping[str, str],
    document_state: DocumentState,
    template_overrides: Mapping[str, Any] | None,
    output_dir: Path,
    copy_assets: bool = True,
    output_name: str | None = None,
    bibliography_path: Path | None = None,
    emitter: DiagnosticEmitter | None = None,
    fragments: list[str] | None = None,
    template_runtime: TemplateRuntime | None = None,
) -> TemplateWrapResult:
    """Wrap LaTeX content using a template and optional asset copying."""
    output_dir = Path(output_dir).resolve()
    resolved_slots = {name: value for name, value in slot_outputs.items()}
    main_slot_content = resolved_slots.get(default_slot, "")
    resolved_slots.setdefault(default_slot, main_slot_content)

    overrides_payload = dict(template_overrides) if template_overrides else None

    template_context = template.prepare_context(
        main_slot_content,
        overrides=overrides_payload,
    )
    root_name: str | None = None
    if output_name:
        root_name = Path(output_name).stem
    if root_name:
        template_context.setdefault("root_filename", root_name)

    for slot_name, content in resolved_slots.items():
        if slot_name == default_slot:
            continue
        template_context[slot_name] = content

    template_context["index_entries"] = document_state.has_index_entries
    index_terms = list(dict.fromkeys(getattr(document_state, "index_entries", [])))
    template_context["has_index"] = bool(index_terms)
    template_context["index_terms"] = [tuple(term) for term in index_terms]

    registry_entries = index_terms
    try:  # pragma: no cover - optional dependency
        from texsmith.index import get_registry
    except ModuleNotFoundError:
        template_context["index_registry"] = [tuple(term) for term in registry_entries]
    else:
        snapshot = sorted(get_registry().snapshot())
        template_context["index_registry"] = [tuple(term) for term in snapshot]
    template_context["acronyms"] = document_state.acronyms.copy()
    template_context["citations"] = list(document_state.citations)
    template_context["bibliography_entries"] = document_state.bibliography
    template_context["requires_shell_escape"] = bool(
        template_context.get("requires_shell_escape", False)
        or getattr(document_state, "requires_shell_escape", False)
    )

    font_yaml_hint = template_context.get("fonts_yaml")
    fonts_yaml_path = Path(font_yaml_hint) if isinstance(font_yaml_hint, (str, Path)) else None
    emitter_obj = ensure_emitter(emitter)
    if fonts_yaml_path and not fonts_yaml_path.exists():
        emitter_obj.warning(f"fonts_yaml override does not exist: {fonts_yaml_path}")
        fonts_yaml_path = None
    font_match = analyse_font_requirements(
        slot_outputs=resolved_slots,
        context=template_context,
        fonts_yaml=fonts_yaml_path,
        check_system=True,
    )
    if font_match:
        available_fonts = list(font_match.present_fonts) or list(font_match.fallback_fonts)
        if not available_fonts:
            available_fonts = ["NotoSans", "NotoColorEmoji"]
        fallback_fonts = list(available_fonts)
        extra_fallbacks = template_context.get("extra_font_fallbacks") or []
        if isinstance(extra_fallbacks, (list, tuple, set)):
            fallback_fonts.extend(str(item) for item in extra_fallbacks if item)
        if fallback_fonts:
            deduped = list(dict.fromkeys(fallback_fonts))
            template_context["fallback_fonts"] = deduped
        template_context.setdefault("present_fonts", list(font_match.present_fonts))
        template_context.setdefault("missing_fonts", list(font_match.missing_fonts))
        template_context.setdefault("font_match_ranges", dict(font_match.font_ranges))
        if font_match.missing_fonts:
            readable = ", ".join(sorted(font_match.missing_fonts))
            emitter_obj.warning(
                f"Missing {len(font_match.missing_fonts)} font families on the system: {readable}."
            )
        if font_match.font_ranges:
            record_event(
                emitter_obj,
                "font_requirements",
                {
                    "required": list(fallback_fonts),
                    "present": list(font_match.present_fonts),
                    "missing": list(font_match.missing_fonts),
                },
            )

    # Render fragments and inject \usepackage declarations.
    source_dir = None
    overrides_press = overrides_payload.get("press") if overrides_payload else None
    if isinstance(overrides_press, Mapping):
        source_dir_raw = overrides_press.get("_source_dir") or overrides_press.get("source_dir")
        if source_dir_raw:
            source_dir = Path(source_dir_raw)
    fragment_names = list(fragments or [])
    if not fragment_names:
        if template_runtime is not None:
            fragment_names = list(template_runtime.extras.get("fragments", []))
        else:
            fragment_names = ["ts-fonts", "ts-callouts"]
    callout_overrides = overrides_payload.get("callouts") if overrides_payload else None
    callouts_defs = normalise_callouts(
        merge_callouts(
            DEFAULT_CALLOUTS, callout_overrides if isinstance(callout_overrides, Mapping) else None
        )
    )
    template_context.setdefault("callouts_definitions", callouts_defs)
    rendered_packages: list[str] = []
    if fragment_names:
        fragment_context: dict[str, Any] = dict(template_context)
        if overrides_payload:
            fragment_context.update(overrides_payload)
            press_section = overrides_payload.get("press")
            if isinstance(press_section, Mapping):
                for key, value in press_section.items():
                    fragment_context.setdefault(key, value)
        rendered_packages, _ = render_fragments(
            fragment_names,
            context=fragment_context,
            output_dir=output_dir,
            source_dir=source_dir,
        )
        template_context["extra_packages"] = "\n".join(
            f"\\usepackage{{{pkg}}}" for pkg in rendered_packages
        )
    else:
        template_context.setdefault("extra_packages", "")

    if document_state.citations and bibliography_path is not None:
        template_context["bibliography"] = bibliography_path.stem
        template_context["bibliography_resource"] = bibliography_path.name
        template_context.setdefault("bibliography_style", "plain")

    latex_output = template.wrap_document(
        main_slot_content,
        context=template_context,
    )

    asset_paths: list[Path] = []
    if copy_assets:
        asset_paths = copy_template_assets(
            template,
            output_dir,
            context=template_context,
            overrides=overrides_payload,
        )

    output_path: Path | None = None
    if output_name:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_name
        output_path.write_text(latex_output, encoding="utf-8")
        template_context.setdefault("root_filename", output_path.stem)

    return TemplateWrapResult(
        latex_output=latex_output,
        template_context=template_context,
        output_path=output_path,
        asset_paths=asset_paths,
    )


__all__ = ["TemplateWrapResult", "wrap_template_document"]
