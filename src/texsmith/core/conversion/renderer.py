"""Template rendering utilities that aggregate conversion fragments."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from texsmith.adapters.latex.latexmk import build_latexmkrc_content

from ..context import DocumentState
from ..diagnostics import DiagnosticEmitter
from ..templates import TemplateError, TemplateRuntime, wrap_template_document
from .debug import debug_enabled, ensure_emitter, raise_conversion_error, record_event


@dataclass(slots=True)
class TemplateFragment:
    """Contract describing the artefacts required by TemplateRenderer."""

    stem: str
    latex: str
    default_slot: str
    slot_outputs: Mapping[str, str]
    slot_includes: set[str] = field(default_factory=set)
    document_state: DocumentState | None = None
    bibliography_path: Path | None = None
    template_engine: str | None = None
    requires_shell_escape: bool = False
    template_overrides: Mapping[str, Any] | None = None
    output_path: Path | None = None
    front_matter: Mapping[str, Any] | None = None
    source_path: Path | None = None
    rule_descriptions: list[dict[str, Any]] | None = None


@dataclass(slots=True)
class TemplateRendererResult:
    """Structured artefacts produced after aggregating slot content."""

    main_tex_path: Path
    fragment_paths: list[Path]
    template_context: dict[str, Any]
    slot_content: dict[str, str]
    document_state: DocumentState
    bibliography_path: Path | None
    template_engine: str | None
    requires_shell_escape: bool
    template_overrides: dict[str, Any] = field(default_factory=dict)
    rule_descriptions: list[dict[str, Any]] = field(default_factory=list)


_SOFT_OVERRIDE_KEYS = {"press._source_dir", "press._source_path"}


class FragmentOverrideError(TemplateError):
    """Raised when fragment template overrides disagree."""


def _merge_overrides(
    target: MutableMapping[str, Any],
    source: Mapping[str, Any],
    *,
    namespace: str = "",
) -> None:
    for key, value in source.items():
        if key not in target:
            target[key] = copy.deepcopy(value)
            continue

        existing = target[key]
        if isinstance(existing, MutableMapping) and isinstance(value, Mapping):
            _merge_overrides(
                existing,
                value,
                namespace=f"{namespace}.{key}" if namespace else key,
            )
            continue

        if existing == value:
            continue

        conflict_path = f"{namespace}.{key}" if namespace else key
        if conflict_path in _SOFT_OVERRIDE_KEYS:
            continue
        raise FragmentOverrideError(
            f"Conflicting template override for '{conflict_path}': {existing!r} vs {value!r}"
        )


def _validate_slots(runtime: TemplateRuntime, aggregated_slots: Mapping[str, Any]) -> None:
    """Ensure that fragments only target declared template slots."""
    declared = set(runtime.slots.keys()) | {runtime.default_slot}
    unknown = sorted(slot for slot in aggregated_slots if slot not in declared)
    if unknown:
        allowed = ", ".join(sorted(declared))
        raise TemplateError(
            f"Fragments target unknown slot(s) {', '.join(unknown)} for template '{runtime.name}'. "
            f"Declared slots: {allowed or '(none)'}."
        )


class TemplateRenderer:
    """Aggregate conversion fragments and wrap them with a template."""

    def __init__(
        self,
        runtime: TemplateRuntime,
        *,
        emitter: DiagnosticEmitter | None = None,
    ) -> None:
        self.runtime = runtime
        self.emitter = ensure_emitter(emitter)

    def _write_latexmkrc(
        self,
        *,
        output_dir: Path,
        main_tex_path: Path,
        template_engine: str | None,
        requires_shell_escape: bool,
        document_state: DocumentState,
        template_context: Mapping[str, Any] | None,
        bibliography_present: bool,
    ) -> Path | None:
        latexmkrc_path = output_dir / ".latexmkrc"
        if latexmkrc_path.exists():
            return latexmkrc_path

        index_engine: str | None = None
        if template_context:
            raw_engine = template_context.get("index_engine")
            if isinstance(raw_engine, str):
                candidate = raw_engine.strip()
                if candidate:
                    index_engine = candidate

        has_index = bool(
            getattr(document_state, "has_index_entries", False)
            or getattr(document_state, "index_entries", [])
        )
        has_glossary = bool(
            getattr(document_state, "acronyms", {}) or getattr(document_state, "glossary", {})
        )

        content = build_latexmkrc_content(
            root_filename=main_tex_path.stem,
            engine=template_engine,
            requires_shell_escape=requires_shell_escape,
            bibliography=bibliography_present,
            index_engine=index_engine,
            has_index=has_index,
            has_glossary=has_glossary,
        )
        try:
            latexmkrc_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            self.emitter.warning(f"Failed to write latexmkrc: {exc}")
            return None
        return latexmkrc_path

    def render(
        self,
        fragments: Sequence[TemplateFragment],
        *,
        output_dir: Path,
        overrides: Mapping[str, Any] | None = None,
        copy_assets: bool = True,
    ) -> TemplateRendererResult:
        if not fragments:
            raise TemplateError("No fragments available for template rendering.")

        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        aggregated_slots: dict[str, list[str]] = {}
        default_slot = self.runtime.default_slot
        aggregated_slots.setdefault(default_slot, [])

        template_overrides: dict[str, Any] | None = None

        shared_state: DocumentState | None = None
        bibliography_path: Path | None = None
        template_engine: str | None = None
        requires_shell_escape = bool(self.runtime.requires_shell_escape)
        rule_descriptions: list[dict[str, Any]] = []

        document_metadata: list[dict[str, Any]] = []

        for fragment in fragments:
            fragment_default_slot = fragment.default_slot or default_slot
            slot_outputs = dict(fragment.slot_outputs)
            if fragment_default_slot not in slot_outputs:
                slot_outputs[fragment_default_slot] = fragment.latex
            fragment_record: dict[str, Any] = {
                "stem": fragment.stem,
                "default_slot": fragment_default_slot,
                "slot_outputs": dict(slot_outputs),
                "index": len(document_metadata),
            }
            if fragment.front_matter:
                fragment_record["front_matter"] = copy.deepcopy(dict(fragment.front_matter))
            if fragment.source_path:
                fragment_record["source_path"] = str(fragment.source_path)
            document_metadata.append(fragment_record)

            for slot_name, latex in slot_outputs.items():
                if not latex:
                    continue
                aggregated_slots.setdefault(slot_name, []).append(latex)

            slot_inclusions = set(fragment.slot_includes or set())
            if slot_inclusions:
                for slot_name in slot_inclusions:
                    aggregated_slots.setdefault(slot_name, [])
                for slot_name in slot_inclusions:
                    if slot_name == fragment_default_slot:
                        continue
                    if fragment.latex:
                        aggregated_slots[slot_name].append(fragment.latex)
                if (
                    fragment_default_slot in slot_inclusions
                    and fragment_default_slot not in slot_outputs
                    and fragment.latex
                ):
                    aggregated_slots[fragment_default_slot].append(fragment.latex)

            fragment_overrides = fragment.template_overrides
            if fragment_overrides:
                if template_overrides is None:
                    template_overrides = dict(fragment_overrides)
                else:
                    _merge_overrides(template_overrides, fragment_overrides)

            if fragment.document_state is not None:
                shared_state = fragment.document_state
            if fragment.bibliography_path is not None:
                bibliography_path = fragment.bibliography_path
            if template_engine is None and fragment.template_engine is not None:
                template_engine = fragment.template_engine
            requires_shell_escape = requires_shell_escape or fragment.requires_shell_escape
            if fragment.rule_descriptions and not rule_descriptions:
                rule_descriptions = list(fragment.rule_descriptions)

        if shared_state is None:
            shared_state = DocumentState()

        slot_content = {
            slot: "\n\n".join(chunks for chunks in content if chunks)
            for slot, content in aggregated_slots.items()
        }

        _validate_slots(self.runtime, slot_content)

        template_instance = self.runtime.instance
        if template_instance is None:  # pragma: no cover - defensive path
            raise TemplateError("Template runtime is missing an instance implementation.")

        if template_overrides is None:
            template_overrides = {}
        if overrides:
            override_dict = dict(overrides)
            _merge_overrides(template_overrides, override_dict)

        if document_metadata:
            if template_overrides is None:
                template_overrides = {}
            template_overrides["documents"] = document_metadata

        if template_overrides:
            record_event(
                self.emitter,
                "template_overrides",
                {"values": dict(template_overrides)},
            )

        main_name = self._resolve_main_name(fragments)
        try:
            wrap_result = wrap_template_document(
                template=template_instance,
                default_slot=default_slot,
                slot_outputs=slot_content,
                document_state=shared_state,
                template_overrides=template_overrides if template_overrides else None,
                output_dir=output_dir,
                copy_assets=copy_assets,
                output_name=main_name,
                bibliography_path=bibliography_path,
                emitter=self.emitter,
                fragments=list(
                    template_overrides.get("fragments", self.runtime.extras.get("fragments", []))
                ),
                template_runtime=self.runtime,
            )
        except TemplateError as exc:
            if debug_enabled(self.emitter):
                raise
            raise_conversion_error(self.emitter, str(exc), exc)

        template_context = wrap_result.template_context or {}
        main_tex_path = wrap_result.output_path or (output_dir / main_name)

        fragment_paths: list[Path] = [
            Path(fragment.output_path) for fragment in fragments if fragment.output_path
        ]

        context_engine: str | None = None
        if template_context:
            raw_engine = template_context.get("latex_engine")
            if isinstance(raw_engine, str):
                stripped = raw_engine.strip()
                if stripped:
                    context_engine = stripped

        template_engine = self.runtime.engine

        if context_engine and context_engine.lower() != "pdflatex":
            template_engine = context_engine
        if template_engine is None:
            template_engine = context_engine or "pdflatex"

        self._write_latexmkrc(
            output_dir=output_dir,
            main_tex_path=main_tex_path,
            template_engine=template_engine,
            requires_shell_escape=requires_shell_escape,
            document_state=shared_state,
            template_context=template_context,
            bibliography_present=bool(bibliography_path),
        )

        return TemplateRendererResult(
            main_tex_path=main_tex_path,
            fragment_paths=fragment_paths,
            template_context=template_context or {},
            slot_content=slot_content,
            document_state=shared_state,
            bibliography_path=bibliography_path,
            template_engine=template_engine,
            requires_shell_escape=requires_shell_escape,
            template_overrides=template_overrides,
            rule_descriptions=rule_descriptions,
        )

    @staticmethod
    def _resolve_main_name(fragments: Sequence[TemplateFragment]) -> str:
        if len(fragments) == 1:
            return f"{fragments[0].stem}.tex"
        first = fragments[0]
        return f"{first.stem}-collection.tex"


__all__ = ["TemplateFragment", "TemplateRenderer", "TemplateRendererResult"]
