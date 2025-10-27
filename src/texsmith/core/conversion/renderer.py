"""Template rendering utilities that aggregate conversion bundles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

from ..context import DocumentState
from ..templates import TemplateError, TemplateRuntime, copy_template_assets

from .debug import _debug_enabled, _fail, _record_event

if TYPE_CHECKING:  # pragma: no cover - typing helpers only
    from texsmith.api.pipeline import ConversionBundle, LaTeXFragment
    from texsmith.core.conversion.debug import ConversionCallbacks


def _merge_overrides(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), Mapping):
            _merge_overrides(target[key], value)
        else:
            target[key] = value


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


class TemplateRenderer:
    """Aggregate conversion fragments and wrap them with a template."""

    def __init__(
        self,
        runtime: TemplateRuntime,
        *,
        callbacks: "ConversionCallbacks | None" = None,
    ) -> None:
        self.runtime = runtime
        self.callbacks = callbacks

    def render(
        self,
        bundle: "ConversionBundle",
        *,
        output_dir: Path,
        overrides: Mapping[str, Any] | None = None,
        copy_assets: bool = True,
    ) -> TemplateRendererResult:
        fragments = list(getattr(bundle, "fragments", []))
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

        for fragment in fragments:
            conversion = getattr(fragment, "conversion", None)
            if conversion is None:
                raise TemplateError(
                    "Conversion bundle is missing conversion metadata for a fragment."
                )

            fragment_default_slot = conversion.default_slot or default_slot
            slot_outputs = dict(conversion.slot_outputs)
            if fragment_default_slot not in slot_outputs:
                slot_outputs[fragment_default_slot] = conversion.latex_output

            for slot_name, latex in slot_outputs.items():
                if not latex:
                    continue
                aggregated_slots.setdefault(slot_name, []).append(latex)

            document_obj = getattr(fragment, "document", None)
            slot_inclusions: set[str] = set()
            if document_obj is not None:
                document_slots = getattr(document_obj, "slots", None)
                if document_slots is not None and hasattr(document_slots, "includes"):
                    slot_inclusions = set(document_slots.includes())
                else:
                    legacy_inclusions = getattr(document_obj, "slot_inclusions", set())
                    slot_inclusions = set(legacy_inclusions)
            if slot_inclusions:
                for slot_name in slot_inclusions:
                    aggregated_slots.setdefault(slot_name, [])
                for slot_name in slot_inclusions:
                    if slot_name == fragment_default_slot:
                        continue
                    if conversion.latex_output:
                        aggregated_slots[slot_name].append(conversion.latex_output)
                if (
                    fragment_default_slot in slot_inclusions
                    and fragment_default_slot not in slot_outputs
                    and conversion.latex_output
                ):
                    aggregated_slots[fragment_default_slot].append(conversion.latex_output)

            if conversion.template_overrides:
                if template_overrides is None:
                    template_overrides = dict(conversion.template_overrides)
                else:
                    _merge_overrides(template_overrides, conversion.template_overrides)

            if conversion.document_state is not None:
                shared_state = conversion.document_state
            if conversion.bibliography_path is not None:
                bibliography_path = conversion.bibliography_path
            if template_engine is None and conversion.template_engine is not None:
                template_engine = conversion.template_engine
            requires_shell_escape = requires_shell_escape or conversion.template_shell_escape

        if shared_state is None:
            shared_state = DocumentState()

        slot_content = {
            slot: "\n\n".join(chunks for chunks in content if chunks)
            for slot, content in aggregated_slots.items()
        }

        main_content = slot_content.get(default_slot, "")

        template_context: dict[str, Any] | None = None
        template_instance = self.runtime.instance
        if template_instance is None:  # pragma: no cover - defensive path
            raise TemplateError("Template runtime is missing an instance implementation.")

        if template_overrides is None:
            template_overrides = {}
        if overrides:
            override_dict = dict(overrides)
            _merge_overrides(template_overrides, override_dict)

        try:
            template_context = template_instance.prepare_context(
                main_content,
                overrides=template_overrides if template_overrides else None,
            )
            for slot_name, content in slot_content.items():
                if slot_name == default_slot:
                    continue
                template_context[slot_name] = content

            template_context["index_entries"] = shared_state.has_index_entries
            template_context["acronyms"] = shared_state.acronyms.copy()
            template_context["citations"] = list(shared_state.citations)
            template_context["bibliography_entries"] = shared_state.bibliography
            if shared_state.citations and bibliography_path is not None:
                template_context["bibliography"] = bibliography_path.stem
                template_context["bibliography_resource"] = bibliography_path.name
                template_context.setdefault("bibliography_style", "plain")

            final_output = template_instance.wrap_document(
                main_content,
                context=template_context,
            )
        except TemplateError as exc:
            if _debug_enabled(self.callbacks):
                raise
            _fail(self.callbacks, str(exc), exc)
            raise

        if template_overrides:
            _record_event(
                self.callbacks,
                "template_overrides",
                {"values": dict(template_overrides)},
            )

        if copy_assets:
            try:
                copy_template_assets(
                    template_instance,
                    output_dir,
                    context=template_context,
                    overrides=template_overrides if template_overrides else None,
                )
            except TemplateError as exc:
                if _debug_enabled(self.callbacks):
                    raise
                _fail(self.callbacks, str(exc), exc)
                raise

        main_name = self._resolve_main_name(fragments)
        main_tex_path = output_dir / main_name
        main_tex_path.write_text(final_output, encoding="utf-8")

        fragment_paths: list[Path] = [
            Path(fragment.output_path) for fragment in fragments if fragment.output_path
        ]

        if template_engine is None:
            template_engine = self.runtime.engine

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
        )

    @staticmethod
    def _resolve_main_name(fragments: Sequence["LaTeXFragment"]) -> str:
        if len(fragments) == 1:
            return f"{fragments[0].stem}.tex"
        first = fragments[0]
        return f"{first.stem}-collection.tex"
