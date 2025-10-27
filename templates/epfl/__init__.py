"""EPFL thesis template integration for texsmith."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from texsmith.core.templates import TemplateError, WrappableTemplate


_PACKAGE_ROOT = Path(__file__).parent.resolve()


class Template(WrappableTemplate):
    """Expose the EPFL thesis template."""

    _DEFAULT_NOTICE = (
        "This is a temporary title page. It will be replaced for the final print "
        "by a version provided by the registrar's office."
    )

    _ABSTRACT_SLOTS = {
        "abstract_en": {"language": "english", "title": "Abstract", "label": "English"},
        "abstract_fr": {"language": "french", "title": "Résumé", "label": "Français"},
        "abstract_de": {"language": "german", "title": "Zusammenfassung", "label": "Deutsch"},
    }

    def __init__(self) -> None:
        try:
            super().__init__(_PACKAGE_ROOT)
        except TemplateError as exc:  # pragma: no cover - defensive
            raise TemplateError(f"Failed to initialise EPFL thesis template: {exc}") from exc

    def prepare_context(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = super().prepare_context(latex_body, overrides=overrides)
        self._apply_metadata(context)
        self._normalise_title(context)
        self._normalise_jury(context)
        self._normalise_supervisors(context)
        self._prepare_languages(context)
        self._prepare_abstracts(context)
        self._clean_optional_sections(context)
        return context

    def wrap_document(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        if context is None:
            context = self.prepare_context(latex_body, overrides=overrides)
        else:
            context = dict(context)
            self._apply_metadata(context)
            self._normalise_title(context)
            self._normalise_jury(context)
            self._normalise_supervisors(context)
            self._prepare_languages(context)
            self._prepare_abstracts(context)
            self._clean_optional_sections(context)
        return super().wrap_document(
            latex_body,
            overrides=overrides,
            context=context,
        )

    def _apply_metadata(self, context: dict[str, Any]) -> None:
        raw_meta = context.get("meta")
        if not isinstance(raw_meta, Mapping):
            return

        payload = raw_meta.get("meta")
        if isinstance(payload, Mapping):
            meta = payload
        else:
            meta = raw_meta

        context.setdefault("title", self._coerce_string(meta.get("title")))
        subtitle = self._coerce_string(meta.get("subtitle"))
        if subtitle:
            context["subtitle"] = subtitle

        author = self._coerce_string(
            meta.get("author") or meta.get("authors") or context.get("author")
        )
        if author:
            context["author"] = author

        thesis_info = meta.get("epfl")
        if isinstance(thesis_info, Mapping):
            for key in (
                "thesis_number",
                "defense_date",
                "faculty",
                "laboratory",
                "doctoral_program",
                "degree",
                "location",
                "title_language",
                "title_notice",
            ):
                value = self._coerce_string(thesis_info.get(key))
                if value:
                    context[key] = value

            supervisors = thesis_info.get("supervisors")
            if supervisors and not context.get("supervisors"):
                context["supervisors"] = list(self._iter_strings(supervisors))

            jury_payload = thesis_info.get("jury")
            if jury_payload and not context.get("jury"):
                context["jury"] = list(self._iter_jury(jury_payload))

            class_options = self._coerce_string(thesis_info.get("class_options"))
            if class_options:
                context["class_options"] = class_options

    def _normalise_title(self, context: dict[str, Any]) -> None:
        title_value = self._coerce_string(context.get("title"))
        subtitle_value = self._coerce_string(context.get("subtitle"))

        if title_value:
            lines = [line.strip() for line in title_value.splitlines() if line.strip()]
        else:
            lines = []
        if not lines:
            lines = ["Thesis Title"]
        context["title_lines"] = lines
        context["subtitle"] = subtitle_value

        notice = self._coerce_string(context.get("title_notice"))
        if not notice:
            notice = self._DEFAULT_NOTICE
        context["title_notice"] = notice

        language = self._coerce_string(context.get("title_language"))
        if not language:
            language = "french"
        context["title_language"] = language

    def _normalise_jury(self, context: dict[str, Any]) -> None:
        entries: list[dict[str, str]] = []
        for entry in self._iter_jury(context.get("jury")):
            name = self._coerce_string(entry.get("name"))
            if not name:
                continue
            role = self._coerce_string(entry.get("role"))
            entries.append({"name": name, "role": role})
        context["jury_entries"] = entries

    def _normalise_supervisors(self, context: dict[str, Any]) -> None:
        supervisors = list(self._iter_strings(context.get("supervisors")))
        context["supervisors"] = supervisors

    def _prepare_abstracts(self, context: dict[str, Any]) -> None:
        sections: list[dict[str, str]] = []
        labels: list[str] = []
        for slot, meta in self._ABSTRACT_SLOTS.items():
            body = self._coerce_string(context.get(slot))
            if not body:
                continue
            label = meta.get("label")
            if label and label not in labels:
                labels.append(label)
            sections.append(
                {
                    "slot": slot,
                    "language": meta["language"],
                    "title": meta["title"],
                    "content": context[slot],
                }
            )
        context["abstract_sections"] = sections
        context["abstract_toc_label"] = "/".join(labels)

    def _prepare_languages(self, context: dict[str, Any]) -> None:
        document_language = self._coerce_string(context.get("language"))
        if not document_language:
            document_language = "english"
        candidates = [document_language, "french", "german"]
        seen: list[str] = []
        for item in candidates:
            token = item.strip()
            if not token:
                continue
            if token not in seen:
                seen.append(token)
        context["document_language"] = seen[0]
        context["babel_languages"] = ",".join(seen)

    def _clean_optional_sections(self, context: dict[str, Any]) -> None:
        for key in (
            "dedication",
            "acknowledgements",
            "preface",
            "cv",
            "frontmatter",
            "backmatter",
            "appendix",
        ):
            value = context.get(key)
            if isinstance(value, str) and not value.strip():
                context[key] = ""

    def _coerce_string(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, Mapping):
            candidate = value.get("text") or value.get("value") or value.get("name")
            return self._coerce_string(candidate)
        if isinstance(value, Iterable) and not isinstance(value, (bytes, str)):
            parts = [self._coerce_string(item) for item in value]
            return ", ".join(part for part in parts if part)
        return str(value).strip()

    def _iter_strings(self, value: Any) -> Iterable[str]:
        if value is None:
            return
        if isinstance(value, str):
            text = value.strip()
            if text:
                yield text
            return
        if isinstance(value, Mapping):
            candidate = value.get("name") or value.get("text") or value.get("value")
            text = self._coerce_string(candidate)
            if text:
                yield text
            return
        if isinstance(value, Iterable) and not isinstance(value, (bytes, str)):
            for item in value:
                yield from self._iter_strings(item)
            return
        text = self._coerce_string(value)
        if text:
            yield text

    def _iter_jury(self, value: Any) -> Iterable[dict[str, str]]:
        if value is None:
            return
        if isinstance(value, Mapping):
            name = self._coerce_string(value.get("name"))
            if not name:
                return
            role = self._coerce_string(value.get("role"))
            yield {"name": name, "role": role}
            return
        if isinstance(value, Iterable) and not isinstance(value, (bytes, str)):
            for item in value:
                if isinstance(item, Mapping):
                    name = self._coerce_string(item.get("name"))
                    if not name:
                        continue
                    role = self._coerce_string(item.get("role"))
                    yield {"name": name, "role": role}
                else:
                    name = self._coerce_string(item)
                    if name:
                        yield {"name": name, "role": ""}
            return
        name = self._coerce_string(value)
        if name:
            yield {"name": name, "role": ""}


__all__ = ["Template"]
