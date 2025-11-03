"""Shared helpers for wrapping LaTeX bodies with template metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Any

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
        from texsmith_index import get_registry
    except ModuleNotFoundError:
        template_context["index_registry"] = [tuple(term) for term in registry_entries]
    else:
        snapshot = sorted(get_registry().snapshot())
        template_context["index_registry"] = [tuple(term) for term in snapshot]
    template_context["acronyms"] = document_state.acronyms.copy()
    template_context["citations"] = list(document_state.citations)
    template_context["bibliography_entries"] = document_state.bibliography

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

    return TemplateWrapResult(
        latex_output=latex_output,
        template_context=template_context,
        output_path=output_path,
        asset_paths=asset_paths,
    )


__all__ = ["TemplateWrapResult", "wrap_template_document"]
