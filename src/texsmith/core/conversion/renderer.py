"""Template rendering utilities that aggregate conversion fragments."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from texsmith.adapters.latex.latexmk import build_latexmkrc_content
from texsmith.fonts import FallbackManager, FontCache, FontPipelineLogger
from texsmith.fonts.fallback import merge_fallback_summaries
from texsmith.fonts.scripts import fallback_summary_to_usage, merge_script_usage

from ..context import DocumentState
from ..diagnostics import DiagnosticEmitter
from ..templates import TemplateError, TemplateRuntime, wrap_template_document
from ..templates.context_usage import summarise_context_usage
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
    assets: dict[str, Path] | None = None


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
    asset_paths: list[Path] = field(default_factory=list)
    asset_sources: list[Path] = field(default_factory=list)
    asset_map: dict[str, Path] = field(default_factory=dict)
    context_attributes: list[dict[str, Any]] = field(default_factory=list)


_SOFT_OVERRIDE_KEYS = {"press._source_dir", "press._source_path", "_source_dir", "_source_path"}


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
        embed_fragments: bool = True,
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
        aggregated_script_usage: list[dict[str, Any]] = []
        aggregated_fallback_summary: list[dict[str, Any]] = []
        bibliography_path: Path | None = None
        template_engine: str | None = None
        requires_shell_escape = bool(self.runtime.requires_shell_escape)
        rule_descriptions: list[dict[str, Any]] = []

        document_metadata: list[dict[str, Any]] = []
        asset_paths: set[Path] = set()
        asset_sources: set[Path] = set()
        asset_map: dict[str, Path] = {}

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
            if fragment.assets:
                for key, path in fragment.assets.items():
                    target_path = Path(path).resolve()
                    asset_map.setdefault(key, target_path)
                    asset_paths.add(target_path)
                    source_candidate = Path(key)
                    if source_candidate.exists():
                        asset_sources.add(source_candidate.resolve())

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
                if shared_state is None:
                    shared_state = fragment.document_state
                else:
                    # Preserve the last state for other fields while merging script usage.
                    pass
                aggregated_script_usage = merge_script_usage(
                    aggregated_script_usage, getattr(fragment.document_state, "script_usage", [])
                )
                aggregated_fallback_summary = merge_fallback_summaries(
                    aggregated_fallback_summary,
                    getattr(fragment.document_state, "fallback_summary", []),
                )
            if fragment.bibliography_path is not None:
                bibliography_path = fragment.bibliography_path
            if template_engine is None and fragment.template_engine is not None:
                template_engine = fragment.template_engine
            requires_shell_escape = requires_shell_escape or fragment.requires_shell_escape
            if fragment.rule_descriptions and not rule_descriptions:
                rule_descriptions = list(fragment.rule_descriptions)

        if shared_state is None:
            shared_state = DocumentState()
        if aggregated_script_usage:
            shared_state.script_usage = merge_script_usage(
                getattr(shared_state, "script_usage", []), aggregated_script_usage
            )
        if aggregated_fallback_summary:
            shared_state.fallback_summary = merge_fallback_summaries(
                getattr(shared_state, "fallback_summary", []), aggregated_fallback_summary
            )

        slot_content: dict[str, str] = {}
        render_slot_content: dict[str, str] = {
            slot: "\n\n".join(chunks for chunks in content if chunks)
            for slot, content in aggregated_slots.items()
        }

        written_fragment_paths: list[Path] = []

        slot_output_overrides: dict[str, str] | None = None

        if embed_fragments:
            slot_content = dict(render_slot_content)
        else:
            slot_inputs: dict[str, list[str]] = {}
            for fragment in fragments:
                fragment_default_slot = fragment.default_slot or default_slot
                slot_outputs = dict(fragment.slot_outputs)
                if fragment_default_slot not in slot_outputs:
                    slot_outputs[fragment_default_slot] = fragment.latex

                for slot_name, latex in slot_outputs.items():
                    if not latex:
                        continue
                    if slot_name == default_slot or slot_name == fragment.stem:
                        filename = f"{fragment.stem}.tex"
                    else:
                        filename = f"{fragment.stem}.{slot_name}.tex"
                    target_path = output_dir / filename
                    try:
                        target_path.write_text(latex, encoding="utf-8")
                        written_fragment_paths.append(target_path)
                        slot_inputs.setdefault(slot_name, []).append(
                            f"\\input{{{target_path.name}}}"
                        )
                    except OSError as exc:
                        raise TemplateError(
                            f"Failed to write fragment '{target_path}': {exc}"
                        ) from exc

                slot_inclusions = set(fragment.slot_includes or set())
                if slot_inclusions:
                    for slot_name in slot_inclusions:
                        if (
                            slot_name == fragment_default_slot
                            and fragment_default_slot not in slot_outputs
                        ):
                            latex = fragment.latex
                            if latex:
                                filename = f"{fragment.stem}.tex"
                                target_path = output_dir / filename
                                try:
                                    target_path.write_text(latex, encoding="utf-8")
                                    written_fragment_paths.append(target_path)
                                except OSError as exc:
                                    raise TemplateError(
                                        f"Failed to write fragment '{target_path}': {exc}"
                                    ) from exc
                                slot_inputs.setdefault(slot_name, []).append(
                                    f"\\input{{{target_path.name}}}"
                                )

            slot_content = {
                slot: "\n".join(entries for entries in slot_inputs.get(slot, []))
                for slot in aggregated_slots
            }
            slot_output_overrides = dict(slot_content)
            aggregated_slots.clear()
            aggregated_slots.update(slot_inputs)

        _validate_slots(self.runtime, render_slot_content)

        # Compute fallback summary across all slot content for font fragments.
        concatenated_text = "".join(render_slot_content.values())
        if concatenated_text:
            try:
                raw_summary = FallbackManager(
                    cache=FontCache(), logger=FontPipelineLogger()
                ).scan_text(concatenated_text)
                if raw_summary:
                    aggregated_fallback_summary = merge_fallback_summaries(
                        aggregated_fallback_summary, raw_summary
                    )
                    usage = fallback_summary_to_usage(raw_summary)
                    if usage:
                        aggregated_script_usage = merge_script_usage(aggregated_script_usage, usage)
                        shared_state.script_usage = merge_script_usage(
                            getattr(shared_state, "script_usage", []), aggregated_script_usage
                        )
                        shared_state.fallback_summary = merge_fallback_summaries(
                            getattr(shared_state, "fallback_summary", []),
                            aggregated_fallback_summary,
                        )
            except Exception:
                # Best-effort: fallback detection should never block rendering.
                pass

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
        if aggregated_script_usage:
            template_overrides = template_overrides or {}
            template_overrides.setdefault("fonts", {})
            if isinstance(template_overrides["fonts"], dict):
                template_overrides["fonts"].setdefault("script_usage", aggregated_script_usage)

        def _iter_strings(value: Any) -> list[str]:
            if isinstance(value, str):
                return [value]
            if isinstance(value, Mapping):
                collected: list[str] = []
                for nested in value.values():
                    collected.extend(_iter_strings(nested))
                return collected
            if isinstance(value, (list, tuple, set)):
                collected: list[str] = []
                for nested in value:
                    collected.extend(_iter_strings(nested))
                return collected
            return []

        metadata_strings: list[str] = []
        for record in document_metadata:
            front_matter = record.get("front_matter")
            if isinstance(front_matter, Mapping):
                metadata_strings.extend(_iter_strings(front_matter))
        if template_overrides:
            metadata_strings.extend(_iter_strings(template_overrides))

        metadata_blob = " ".join(part for part in metadata_strings if part.strip())
        if metadata_blob:
            try:
                metadata_raw = FallbackManager(
                    cache=FontCache(), logger=FontPipelineLogger()
                ).scan_text(metadata_blob)
            except Exception:
                metadata_raw = []
            if metadata_raw:
                aggregated_fallback_summary = merge_fallback_summaries(
                    aggregated_fallback_summary, metadata_raw
                )
                metadata_usage = fallback_summary_to_usage(metadata_raw)
                if metadata_usage:
                    aggregated_script_usage = merge_script_usage(
                        aggregated_script_usage, metadata_usage
                    )
                    shared_state.script_usage = merge_script_usage(
                        getattr(shared_state, "script_usage", []), aggregated_script_usage
                    )
                shared_state.fallback_summary = merge_fallback_summaries(
                    getattr(shared_state, "fallback_summary", []), aggregated_fallback_summary
                )

        if aggregated_script_usage or aggregated_fallback_summary:
            template_overrides = template_overrides or {}
            template_overrides.setdefault("fonts", {})
            if isinstance(template_overrides["fonts"], dict):
                if aggregated_script_usage:
                    existing_usage = template_overrides["fonts"].get("script_usage", [])
                    template_overrides["fonts"]["script_usage"] = merge_script_usage(
                        existing_usage if isinstance(existing_usage, list) else [],
                        aggregated_script_usage,
                    )
                if aggregated_fallback_summary:
                    existing_fallback = template_overrides["fonts"].get("fallback_summary", [])
                    template_overrides["fonts"]["fallback_summary"] = merge_fallback_summaries(
                        existing_fallback if isinstance(existing_fallback, list) else [],
                        aggregated_fallback_summary,
                    )

        main_name = self._resolve_main_name(fragments)
        try:
            wrap_result = wrap_template_document(
                template=template_instance,
                default_slot=default_slot,
                slot_outputs=render_slot_content,
                slot_output_overrides=slot_output_overrides,
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
        fragment_paths.extend(written_fragment_paths)
        asset_paths.update(wrap_result.asset_paths or [])
        for source, destination in getattr(wrap_result, "asset_pairs", []):
            resolved_dest = Path(destination).resolve()
            asset_paths.add(resolved_dest)
            asset_sources.add(Path(source).resolve())
            asset_map.setdefault(str(source), resolved_dest)

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

        template_context.setdefault("latex_engine", template_engine)

        self._write_latexmkrc(
            output_dir=output_dir,
            main_tex_path=main_tex_path,
            template_engine=template_engine,
            requires_shell_escape=requires_shell_escape,
            document_state=shared_state,
            template_context=template_context,
            bibliography_present=bool(bibliography_path),
        )

        asset_path_list = sorted({path.resolve() for path in asset_paths})
        asset_source_list = sorted({path.resolve() for path in asset_sources})

        context_attributes = summarise_context_usage(
            template_instance,
            template_context,
            fragment_names=wrap_result.rendered_fragments,
            overrides=template_overrides,
        )

        return TemplateRendererResult(
            main_tex_path=main_tex_path,
            fragment_paths=fragment_paths,
            template_context=template_context or {},
            slot_content=slot_output_overrides or slot_content,
            document_state=shared_state,
            bibliography_path=bibliography_path,
            template_engine=template_engine,
            requires_shell_escape=requires_shell_escape,
            template_overrides=template_overrides,
            rule_descriptions=rule_descriptions,
            asset_paths=asset_path_list,
            asset_sources=asset_source_list,
            asset_map=asset_map,
            context_attributes=context_attributes,
        )

    @staticmethod
    def _resolve_main_name(fragments: Sequence[TemplateFragment]) -> str:
        if len(fragments) == 1:
            return f"{fragments[0].stem}.tex"
        return "main.tex"


__all__ = ["TemplateFragment", "TemplateRenderer", "TemplateRendererResult"]
