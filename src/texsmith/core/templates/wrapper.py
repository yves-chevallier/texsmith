"""Shared helpers for wrapping LaTeX bodies with template metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from jinja2 import meta

from texsmith.core.callouts import DEFAULT_CALLOUTS, merge_callouts, normalise_callouts
from texsmith.core.fragments import (
    FRAGMENT_REGISTRY,
    inject_fragment_attributes,
    render_fragments,
)
from texsmith.core.templates import TemplateRuntime
from texsmith.core.templates.manifest import TemplateError

from texsmith.core.conversion.debug import ensure_emitter
from texsmith.core.diagnostics import DiagnosticEmitter
from texsmith.fonts.scripts import render_script_macros
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
    asset_pairs: list[tuple[Path, Path]] = field(default_factory=list)
    rendered_fragments: list[str] = field(default_factory=list)


def wrap_template_document(
    *,
    template: WrappableTemplate,
    default_slot: str,
    slot_outputs: Mapping[str, str],
    slot_output_overrides: Mapping[str, str] | None = None,
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
    override_slots = (
        {name: value for name, value in slot_output_overrides.items()}
        if slot_output_overrides
        else None
    )
    def _process_slot(value: Any) -> Any:
        return value

    main_slot_content = _process_slot(resolved_slots.get(default_slot, ""))
    resolved_slots[default_slot] = main_slot_content
    resolved_slots.setdefault(default_slot, main_slot_content)
    processed_override_slots: dict[str, Any] | None = None
    if override_slots is not None:
        processed_override_slots = {
            name: _process_slot(value) for name, value in override_slots.items()
        }
        processed_override_slots.setdefault(
            default_slot, resolved_slots.get(default_slot, "")
        )

    overrides_payload = dict(template_overrides) if template_overrides else None
    source_dir = None
    overrides_press = overrides_payload.get("press") if overrides_payload else None
    if isinstance(overrides_payload, Mapping):
        raw_source_dir = overrides_payload.get("_source_dir") or overrides_payload.get("source_dir")
        if isinstance(raw_source_dir, (str, Path)) and str(raw_source_dir):
            source_dir = Path(raw_source_dir)
    if source_dir is None and isinstance(overrides_press, Mapping):
        source_dir_raw = overrides_press.get("_source_dir") or overrides_press.get("source_dir")
        if source_dir_raw:
            source_dir = Path(source_dir_raw)
    fragment_names = list(fragments or [])
    if not fragment_names:
        if template_runtime is not None:
            fragment_names = list(template_runtime.extras.get("fragments") or [])
        else:
            manifest_fragments = getattr(template.info, "fragments", None)
            fragment_names = list(manifest_fragments or [])

    template_context = template.prepare_context(
        main_slot_content,
        overrides=overrides_payload,
    )
    if isinstance(overrides_press, Mapping):
        template_context.setdefault("press", overrides_press)
    root_name: str | None = None
    if output_name:
        root_name = Path(output_name).stem
    if root_name:
        template_context.setdefault("root_filename", root_name)

    for slot_name, raw_content in resolved_slots.items():
        if slot_name == default_slot:
            continue
        processed_content = _process_slot(raw_content)
        resolved_slots[slot_name] = processed_content
        template_context[slot_name] = processed_content

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

    fragment_attributes: dict[str, Any] = {}
    if fragment_names:
        fragment_attributes = inject_fragment_attributes(
            fragment_names,
            context=template_context,
            overrides=overrides_payload,
            source_dir=source_dir,
            declared_attribute_owners=(
                template.info.attribute_owners() if hasattr(template, "info") else {}
            ),
        )

    code_section = template_context.get("code")
    code_engine = None
    code_style = "bw"
    if isinstance(code_section, Mapping):
        raw_engine = code_section.get("engine")
        code_engine = raw_engine if isinstance(raw_engine, str) else None
        raw_style = code_section.get("style")
        if isinstance(raw_style, str) and raw_style.strip():
            code_style = raw_style.strip()
    elif isinstance(code_section, str):
        code_engine = code_section
    code_engine = (code_engine or "pygments").strip().lower()
    template_context["code_engine"] = code_engine or "pygments"
    template_context.setdefault("code_style", code_style)
    if "code" not in template_context:
        template_context["code"] = {
            "engine": template_context["code_engine"],
            "style": template_context["code_style"],
        }
    elif isinstance(template_context["code"], dict):
        template_context["code"].setdefault("style", template_context["code_style"])
    if code_engine == "pygments" and getattr(document_state, "pygments_styles", {}):
        styles = getattr(document_state, "pygments_styles", {})
        template_context["pygments_style_defs"] = "\n".join(styles.values())

    template_context["requires_shell_escape"] = bool(
        template_context.get("requires_shell_escape", False)
        or getattr(document_state, "requires_shell_escape", False)
        or (template_runtime.requires_shell_escape if template_runtime else False)
        or code_engine == "minted"
    )
    if template_runtime and template_runtime.engine:
        template_context.setdefault("latex_engine", template_runtime.engine)

    emitter_obj = ensure_emitter(emitter)

    if document_state.citations and bibliography_path is not None:
        template_context["bibliography"] = bibliography_path.stem
        template_context["bibliography_resource"] = bibliography_path.name
        template_context.setdefault("bibliography_style", "numeric")

    template_context["ts_uses_callouts"] = bool(getattr(document_state, "callouts_used", False))

    # Render fragments and inject declarations into template variables.
    requested_fragments = list(fragment_names)
    callout_overrides = overrides_payload.get("callouts") if overrides_payload else None
    callouts_defs = normalise_callouts(
        merge_callouts(
            DEFAULT_CALLOUTS, callout_overrides if isinstance(callout_overrides, Mapping) else None
        )
    )
    template_context.setdefault("callouts_definitions", callouts_defs)
    variable_injections: dict[str, list[str]] = {}
    fragment_providers: dict[str, list[str]] = {}
    declared_slots, _default_slot = template.info.resolve_slots()
    declared_slot_names = set(declared_slots.keys())
    declared_vars = _discover_template_variables(template)
    rendered_fragments: set[str] = set()
    if fragment_names:
        fragment_context: dict[str, Any] = template_context

        def _reassert_effective_emoji_mode(target: dict[str, Any]) -> None:
            effective_mode = target.get("_texsmith_effective_emoji_mode")
            if not effective_mode:
                return
            target["emoji"] = effective_mode
            target["emoji_mode"] = effective_mode
            fonts_section = target.get("fonts")
            if isinstance(fonts_section, Mapping):
                if isinstance(fonts_section, dict):
                    fonts_section["emoji"] = effective_mode
                else:
                    updated_fonts = dict(fonts_section)
                    updated_fonts["emoji"] = effective_mode
                    target["fonts"] = updated_fonts

        if overrides_payload:
            for key, value in overrides_payload.items():
                if key in fragment_attributes:
                    continue
                fragment_context.setdefault(key, value)
            press_section = overrides_payload.get("press")
            if isinstance(press_section, Mapping):
                for key, value in press_section.items():
                    fragment_context.setdefault(key, value)
            _reassert_effective_emoji_mode(fragment_context)
        else:
            _reassert_effective_emoji_mode(fragment_context)
        fragment_result = render_fragments(
            fragment_names,
            context=fragment_context,
            output_dir=output_dir,
            source_dir=source_dir,
            overrides=overrides_payload,
            declared_slots=declared_slot_names,
            declared_variables=declared_vars,
            template_name=template.info.name,
        )
        variable_injections = fragment_result.variable_injections
        fragment_providers = fragment_result.providers
        for provider_list in fragment_providers.values():
            rendered_fragments.update(provider_list)
    template_context["requested_fragments"] = requested_fragments
    template_context["fragments"] = sorted(rendered_fragments)

    if variable_injections:
        for variable_name, injections in variable_injections.items():
            base = template_context.get(variable_name, "")
            parts: list[str] = [base] if base else []
            parts.extend(injections)
            template_context[variable_name] = "\n".join(part for part in parts if part)

    script_macros = render_script_macros(getattr(document_state, "script_usage", []))
    if script_macros:
        existing_extra = template_context.get("extra_packages", "")
        template_context["extra_packages"] = "\n".join(
            part for part in (existing_extra, script_macros) if part
        )
        template_context["script_macros"] = script_macros

    final_slots = processed_override_slots if processed_override_slots is not None else resolved_slots
    for slot_name, value in final_slots.items():
        template_context[slot_name] = value
    main_slot_content = final_slots.get(default_slot, main_slot_content)

    # Append pdfLaTeX-specific packages when not using LuaLaTeX.
    extra_lines = [line for line in template_context.get("extra_packages", "").splitlines() if line]
    engine = str(template_context.get("latex_engine") or "").strip().lower()
    if engine and engine != "lualatex":
        for package in template_context.get("pdflatex_extra_packages") or []:
            if package:
                extra_lines.append(f"\\usepackage{{{package}}}")
    template_context["extra_packages"] = "\n".join(extra_lines)

    if document_state.citations and bibliography_path is not None:
        template_context["bibliography"] = bibliography_path.stem
        template_context["bibliography_resource"] = bibliography_path.name
        template_context.setdefault("bibliography_style", "plain")

    latex_output = template.wrap_document(
        main_slot_content,
        context=template_context,
    )
    latex_output = _squash_blank_lines(latex_output)

    asset_paths: list[Path] = []
    asset_pairs: list[tuple[Path, Path]] = []
    if copy_assets:
        declared_assets = list(template.iter_assets())
        asset_paths = copy_template_assets(
            template,
            output_dir,
            context=template_context,
            overrides=overrides_payload,
            assets=declared_assets,
        )
        asset_pairs = [(entry.source, dest) for entry, dest in zip(declared_assets, asset_paths)]

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
        asset_pairs=asset_pairs,
        rendered_fragments=sorted(rendered_fragments),
    )


def _discover_template_variables(template: WrappableTemplate) -> set[str] | None:
    """Return undeclared variables referenced by the template entrypoint."""
    env = template.environment
    try:
        source, _, _ = env.loader.get_source(env, template.info.entrypoint)
    except Exception:
        return None
    parsed = env.parse(source)
    return set(meta.find_undeclared_variables(parsed))


def _squash_blank_lines(text: str) -> str:
    """Normalise LaTeX output by trimming trailing whitespace and blank lines."""
    trimmed = re.sub(r"[ \t]+(?=\r?\n|$)", "", text)
    return re.sub(r"\n{3,}", "\n\n", trimmed)


__all__ = ["TemplateWrapResult", "wrap_template_document"]
