"""Springer Nature article template integration for texsmith."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from texsmith.templates import TemplateError, WrappableTemplate
from texsmith.utils import escape_latex_chars


_PACKAGE_ROOT = Path(__file__).parent.resolve()


class Template(WrappableTemplate):
    """Expose the Springer Nature article template."""

    _DEFAULT_CLASS_OPTIONS = ("sn-mathphys-num",)
    _REFERENCE_STYLES = {
        "sn-basic",
        "sn-mathphys-num",
        "sn-mathphys-ay",
        "sn-aps",
        "sn-apacite",
        "sn-chicago",
        "sn-vancouver-num",
        "sn-vancouver-ay",
        "sn-nature",
    }
    _DEFAULT_REFERENCE_STYLE = "sn-mathphys-num"

    def __init__(self) -> None:
        try:
            super().__init__(_PACKAGE_ROOT)
        except TemplateError as exc:
            raise TemplateError(f"Failed to initialise SN article template: {exc}") from exc

    def prepare_context(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = super().prepare_context(latex_body, overrides=overrides)
        self._apply_metadata(context)
        context.setdefault("author_entries", [])
        context.setdefault("affiliation_entries", [])

        class_options = list(self._normalise_class_options(context.get("class_options")))

        bibliography_style = self._normalise_reference_style(context.get("bibliography_style"))
        if bibliography_style and bibliography_style not in class_options:
            class_options.append(bibliography_style)

        context["class_options"] = ",".join(option for option in class_options if option)
        context["bibliography_style"] = bibliography_style

        bibliography = self._coerce_string(context.get("bibliography"))
        context["bibliography"] = bibliography or "sn-bibliography"

        return context

    def _apply_metadata(self, context: dict[str, Any]) -> None:
        raw_meta = context.get("meta")
        if not isinstance(raw_meta, Mapping):
            return

        nested_meta = raw_meta.get("meta") if isinstance(raw_meta.get("meta"), Mapping) else None
        meta_payload: Mapping[str, Any] = nested_meta or raw_meta

        title = self._coerce_string(meta_payload.get("title"))
        if title:
            escaped_title = escape_latex_chars(title)
            context["title"] = escaped_title
            if not self._coerce_string(context.get("short_title")):
                context["short_title"] = escaped_title

        subtitle = self._coerce_string(meta_payload.get("subtitle"))
        if subtitle:
            context["subtitle"] = escape_latex_chars(subtitle)

        short_title = self._coerce_string(meta_payload.get("short_title"))
        if short_title:
            context["short_title"] = escape_latex_chars(short_title)

        (
            author_display,
            author_entries,
            affiliation_entries,
        ) = self._normalise_authors(
            meta_payload.get("authors"),
            meta_payload.get("affiliations"),
        )

        if author_display:
            context["author"] = author_display
        else:
            fallback_author = self._coerce_string(meta_payload.get("author"))
            if fallback_author:
                context["author"] = escape_latex_chars(fallback_author)

        if author_entries:
            context["author_entries"] = author_entries
        if affiliation_entries:
            context["affiliation_entries"] = affiliation_entries

        date_value = self._coerce_string(meta_payload.get("date"))
        if date_value:
            context["date"] = escape_latex_chars(date_value)

        abstract_value = self._coerce_string(meta_payload.get("abstract"))
        if abstract_value:
            context["abstract"] = escape_latex_chars(abstract_value)

        keywords_value = self._format_keywords(meta_payload.get("keywords"))
        if keywords_value:
            context["keywords"] = keywords_value

        bibliography_value = self._coerce_string(meta_payload.get("bibliography"))
        if bibliography_value:
            context["bibliography"] = bibliography_value

        style_value = self._coerce_string(
            meta_payload.get("bibliography_style")
            or meta_payload.get("reference_style")
            or meta_payload.get("citation_style")
        )
        if style_value:
            context["bibliography_style"] = style_value

        class_options = meta_payload.get("class_options") or meta_payload.get("options")
        if class_options is not None:
            context["class_options"] = self._stringify_options(class_options)

        context.pop("meta", None)
        context.pop("authors", None)

    def _coerce_string(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            candidate = value.strip()
        else:
            candidate = str(value).strip()
        return candidate or None

    def _stringify_options(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            tokens = []
            for item in value:
                token = self._coerce_string(item)
                if token:
                    tokens.append(token)
            return ",".join(tokens)
        return str(value).strip()

    def _format_keywords(self, payload: Any) -> str | None:
        if payload is None:
            return None

        if isinstance(payload, str):
            candidate = payload.strip()
            return escape_latex_chars(candidate) if candidate else None

        if isinstance(payload, Mapping):
            payload = payload.values()

        if isinstance(payload, Iterable):
            keywords: list[str] = []
            for item in payload:
                token = self._coerce_string(item)
                if not token:
                    continue
                keywords.append(escape_latex_chars(token))
            if keywords:
                return ", ".join(keywords)
            return None

        return None

    def _normalise_authors(
        self,
        payload: Any,
        additional_affiliations: Any | None = None,
    ) -> tuple[str | None, list[dict[str, Any]], list[dict[str, str]]]:
        if payload is None and additional_affiliations is None:
            return (None, [], [])

        if isinstance(payload, str):
            candidate = payload.strip()
            if candidate:
                return (escape_latex_chars(candidate), [], [])
            return (None, [], [])

        if isinstance(payload, Mapping):
            candidates = [payload]
        elif isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            candidates = list(payload)
        elif payload is None:
            candidates = []
        else:
            display = self._coerce_string(payload)
            return (escape_latex_chars(display) if display else None, [], [])

        affiliation_ids: dict[str, str] = {}
        affiliations: list[dict[str, str]] = []
        author_entries: list[dict[str, Any]] = []
        fallback_names: list[str] = []

        def ensure_affiliation(raw_affiliation: str) -> str:
            if raw_affiliation in affiliation_ids:
                return affiliation_ids[raw_affiliation]
            identifier = str(len(affiliation_ids) + 1)
            affiliation_ids[raw_affiliation] = identifier
            affiliations.append(
                {
                    "id": identifier,
                    "text": escape_latex_chars(raw_affiliation),
                }
            )
            return identifier

        for item in candidates:
            if isinstance(item, str):
                name_value = self._coerce_string(item)
                if name_value:
                    fallback_names.append(escape_latex_chars(name_value))
                continue

            if not isinstance(item, Mapping):
                continue

            name_value = self._coerce_string(
                item.get("name")
                or item.get("full_name")
                or item.get("fullname")
                or item.get("display")
            )
            if not name_value:
                continue

            escaped_name = escape_latex_chars(name_value)
            fallback_names.append(escaped_name)

            indices: list[str] = []
            raw_affiliations = item.get("affiliations") or item.get("affiliation")
            for affiliation in self._iter_affiliations(raw_affiliations):
                aff_value = self._coerce_string(affiliation)
                if not aff_value:
                    continue
                idx = ensure_affiliation(aff_value)
                if idx not in indices:
                    indices.append(idx)

            email_value = self._coerce_string(
                item.get("email") or item.get("mail") or item.get("contact")
            )
            escaped_email = escape_latex_chars(email_value) if email_value else None

            corresponding_flag = (
                item.get("corresponding")
                if "corresponding" in item
                else item.get("is_corresponding")
            )
            if corresponding_flag is None:
                corresponding_flag = item.get("primary")

            corresponding = self._coerce_bool(corresponding_flag)

            equal_note = self._coerce_string(
                item.get("equal_contrib")
                or item.get("equal_contribution")
                or item.get("contribution_note")
            )
            if equal_note:
                equal_note = escape_latex_chars(equal_note)

            author_entries.append(
                {
                    "name": escaped_name,
                    "indices": indices,
                    "email": escaped_email,
                    "corresponding": corresponding,
                    "equal_note": equal_note,
                }
            )

        for extra in self._iter_affiliations(additional_affiliations):
            extra_text = self._coerce_string(extra)
            if not extra_text:
                continue
            ensure_affiliation(extra_text)

        if not author_entries:
            display = " \\and ".join(fallback_names) if fallback_names else None
            return (display, [], affiliations)

        if not any(entry["corresponding"] for entry in author_entries):
            author_entries[0]["corresponding"] = True

        display_names = " \\and ".join(entry["name"] for entry in author_entries)

        return (display_names, author_entries, affiliations)

    def _iter_affiliations(self, payload: Any) -> Iterable[str]:
        if payload is None:
            return

        if isinstance(payload, str):
            yield payload
            return

        if isinstance(payload, Mapping):
            candidate = (
                payload.get("text")
                or payload.get("name")
                or payload.get("organization")
                or payload.get("organisation")
                or payload.get("institution")
                or payload.get("value")
            )
            coerced = self._coerce_string(candidate)
            if coerced:
                yield coerced
            return

        if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            for item in payload:
                yield from self._iter_affiliations(item)
            return

        coerced = self._coerce_string(payload)
        if coerced:
            yield coerced

    def _coerce_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            token = value.strip().lower()
            if token in {"", "0", "false", "no", "n"}:
                return False
            if token in {"true", "yes", "y", "1"}:
                return True
            return False
        return bool(value)

    def _normalise_class_options(self, value: Any) -> tuple[str, ...]:
        raw = self._stringify_options(value)
        if not raw:
            return self._DEFAULT_CLASS_OPTIONS

        options = [token.strip() for token in raw.split(",") if token.strip()]
        return tuple(dict.fromkeys(options))

    def _normalise_reference_style(self, value: Any) -> str:
        candidate = self._coerce_string(value)
        if not candidate:
            return self._DEFAULT_REFERENCE_STYLE

        if candidate not in self._REFERENCE_STYLES:
            allowed = ", ".join(sorted(self._REFERENCE_STYLES))
            raise TemplateError(
                "Invalid bibliography style "
                f"'{candidate}' for SN article template. Allowed values: {allowed}."
            )
        return candidate


__all__ = ["Template"]
