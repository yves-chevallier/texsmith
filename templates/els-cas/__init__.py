"""Elsevier CAS template integration for texsmith."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Mapping

from texsmith.templates import TemplateError, WrappableTemplate
from texsmith.utils import escape_latex_chars


_PACKAGE_ROOT = Path(__file__).parent.resolve()


class Template(WrappableTemplate):
    """Expose the Elsevier CAS template as a wrappable template instance."""

    _COLUMN_MODES = {
        "single": "cas-sc",
        "double": "cas-dc",
        "sc": "cas-sc",
        "dc": "cas-dc",
    }

    _AFFILIATION_FIELDS = {
        "organization",
        "institution",
        "department",
        "addressline",
        "city",
        "state",
        "province",
        "postcode",
        "postal_code",
        "country",
        "email",
    }

    def __init__(self) -> None:
        try:
            super().__init__(_PACKAGE_ROOT)
        except TemplateError as exc:
            raise TemplateError(
                f"Failed to initialise Elsevier CAS template: {exc}"
            ) from exc

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
        context.setdefault("correspondence_entries", [])
        context.setdefault("footnote_entries", [])

        column_mode = self._normalise_column_mode(context.get("column_mode"))
        context["documentclass_name"] = column_mode

        long_title = bool(context.get("long_title"))
        options = ["a4paper", "fleqn"]
        if long_title:
            options.append("longmktitle")
        context["documentclass_options"] = ",".join(options)

        keywords = context.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [token.strip() for token in keywords.split(",") if token.strip()]
        context["keywords"] = [escape_latex_chars(item) for item in keywords]
        context["keywords_joined"] = r" \sep ".join(context["keywords"])

        highlights = self._normalise_highlights(context.get("highlights"))
        context["highlights"] = highlights

        bibliography = self._coerce_string(context.get("bibliography"))
        context["bibliography"] = bibliography or "cas-refs"

        bibliography_style = self._coerce_string(context.get("bibliography_style"))
        context["bibliography_style"] = bibliography_style or "cas-model2-names"

        author_entries = context.get("author_entries") or []
        if isinstance(author_entries, list):
            short_names = [
                entry.get("short_name") or entry.get("name") for entry in author_entries
            ]
            default_short_authors = ", ".join(filter(None, short_names))
        else:
            default_short_authors = ""
        context["default_short_authors"] = default_short_authors

        if not self._coerce_string(context.get("short_authors")):
            context["short_authors"] = default_short_authors

        if not self._coerce_string(context.get("short_title")):
            context["short_title"] = context.get("title", "")

        abstract_value = self._coerce_string(context.get("abstract"))
        context["abstract"] = abstract_value or ""

        return context

    def _apply_metadata(self, context: dict[str, Any]) -> None:
        raw_meta = context.get("meta")
        if isinstance(raw_meta, Mapping):
            meta_payload: Mapping[str, Any] = raw_meta.get("meta", raw_meta)
        else:
            meta_payload = {}

        title = self._coerce_string(meta_payload.get("title"))
        if title:
            context["title"] = escape_latex_chars(title)

        subtitle = self._coerce_string(meta_payload.get("subtitle"))
        if subtitle:
            context["subtitle"] = escape_latex_chars(subtitle)

        short_title = self._coerce_string(
            meta_payload.get("short_title") or context.get("short_title")
        )
        if short_title:
            context["short_title"] = escape_latex_chars(short_title)

        short_authors = self._coerce_string(meta_payload.get("short_authors"))
        if short_authors:
            context["short_authors"] = escape_latex_chars(short_authors)

        date_value = self._coerce_string(meta_payload.get("date"))
        if date_value:
            context["date"] = escape_latex_chars(date_value)

        abstract_value = self._coerce_string(
            meta_payload.get("abstract") or context.get("abstract")
        )
        if abstract_value:
            context["abstract"] = escape_latex_chars(abstract_value)

        highlights = meta_payload.get("highlights")
        if highlights is not None:
            context["highlights"] = highlights

        keywords = meta_payload.get("keywords")
        if keywords is not None:
            context["keywords"] = keywords

        bibliography_value = self._coerce_string(meta_payload.get("bibliography"))
        if bibliography_value:
            context["bibliography"] = bibliography_value

        bibliography_style = self._coerce_string(meta_payload.get("bibliography_style"))
        if bibliography_style:
            context["bibliography_style"] = bibliography_style

        column_mode_raw = (
            meta_payload.get("column_mode")
            or meta_payload.get("layout")
            or context.get("column_mode")
        )
        if column_mode_raw is not None:
            context["column_mode"] = column_mode_raw

        long_title_flag = meta_payload.get("long_title")
        if long_title_flag is not None:
            context["long_title"] = bool(long_title_flag)

        title_note = self._coerce_string(meta_payload.get("title_note"))
        if title_note:
            context["title_note"] = {
                "mark": "1",
                "text": escape_latex_chars(title_note),
            }

        graphical = self._coerce_string(meta_payload.get("graphical_abstract"))
        if graphical:
            context["graphical_abstract"] = escape_latex_chars(graphical)

        author_payload = meta_payload.get("authors") or meta_payload.get("author")
        if author_payload is not None:
            (
                author_entries,
                affiliation_entries,
                correspondence_entries,
                footnote_entries,
            ) = self._normalise_authors(
                author_payload,
                meta_payload.get("affiliations"),
            )
            context["author_entries"] = author_entries
            context["affiliation_entries"] = affiliation_entries
            context["correspondence_entries"] = correspondence_entries
            context["footnote_entries"] = footnote_entries

        context.pop("meta", None)

    def _normalise_column_mode(self, value: Any) -> str:
        if value is None:
            return self._COLUMN_MODES["double"]

        if isinstance(value, str):
            key = value.strip().lower()
            mapped = self._COLUMN_MODES.get(key)
            if mapped:
                return mapped
        elif isinstance(value, (int, float)):
            numeric = int(value)
            if numeric == 1:
                return self._COLUMN_MODES["single"]
            if numeric == 2:
                return self._COLUMN_MODES["double"]

        allowed = ", ".join(sorted({"single", "double"}))
        raise TemplateError(
            f"Invalid column mode '{value}' for Elsevier CAS template. "
            f"Allowed values: {allowed}."
        )

    def _normalise_highlights(self, payload: Any) -> list[str]:
        if payload is None:
            return []

        if isinstance(payload, str):
            candidates = [item.strip() for item in payload.split("\n") if item.strip()]
        elif isinstance(payload, Mapping):
            candidates = [
                self._coerce_string(value)
                for value in payload.values()
                if self._coerce_string(value)
            ]
        elif isinstance(payload, Iterable):
            candidates = [
                self._coerce_string(item)
                for item in payload
                if self._coerce_string(item)
            ]
        else:
            candidates = []

        return [escape_latex_chars(item) for item in candidates if item]

    def _normalise_authors(
        self,
        payload: Any,
        additional_affiliations: Any | None = None,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, str]],
        list[dict[str, str]],
    ]:
        if payload is None:
            return ([], [], [], [])

        if isinstance(payload, Mapping):
            candidates = [payload]
        elif isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            candidates = list(payload)
        elif isinstance(payload, str):
            coerced = self._coerce_string(payload)
            if not coerced:
                return ([], [], [], [])
            return (
                [
                    {
                        "name": escape_latex_chars(coerced),
                        "indices": [],
                        "indices_str": "",
                        "email": None,
                        "url": None,
                        "orcid": None,
                        "credit": None,
                        "corr_mark": None,
                        "footnote_mark": None,
                        "short_name": escape_latex_chars(coerced),
                    }
                ],
                [],
                [],
                [],
            )
        else:
            return ([], [], [], [])

        affiliation_registry: dict[str, dict[str, Any]] = {}
        affiliation_order: list[str] = []
        correspondence_entries: list[dict[str, str]] = []
        footnote_entries: list[dict[str, str]] = []

        def register_affiliation(spec: Any) -> str:
            key, entry = self._coerce_affiliation(spec)
            if key in affiliation_registry:
                return affiliation_registry[key]["id"]
            identifier = str(len(affiliation_registry) + 1)
            entry["id"] = identifier
            entry["render"] = self._render_affiliation(entry)
            affiliation_registry[key] = entry
            affiliation_order.append(key)
            return identifier

        if additional_affiliations is not None:
            if isinstance(additional_affiliations, Mapping):
                iterable = additional_affiliations.values()
            elif isinstance(additional_affiliations, Iterable) and not isinstance(
                additional_affiliations, (str, bytes)
            ):
                iterable = additional_affiliations
            else:
                iterable = [additional_affiliations]
            for item in iterable:
                register_affiliation(item)

        author_entries: list[dict[str, Any]] = []
        corr_counter = 1
        footnote_counter = 1

        for item in candidates:
            if isinstance(item, str):
                name_value = self._coerce_string(item)
                if not name_value:
                    continue
                escaped_name = escape_latex_chars(name_value)
                author_entries.append(
                    {
                        "name": escaped_name,
                        "indices": [],
                        "indices_str": "",
                        "email": None,
                        "url": None,
                        "orcid": None,
                        "credit": None,
                        "corr_mark": None,
                        "footnote_mark": None,
                        "short_name": escaped_name,
                    }
                )
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
            affiliations_raw = item.get("affiliations") or item.get("affiliation")
            indices: list[str] = []
            for spec in self._iter_affiliations(affiliations_raw):
                idx = register_affiliation(spec)
                if idx not in indices:
                    indices.append(idx)

            email_value = self._coerce_string(item.get("email"))
            url_value = self._coerce_string(
                item.get("url") or item.get("homepage") or item.get("website")
            )
            orcid_value = self._coerce_string(item.get("orcid"))
            credit_value = self._coerce_string(
                item.get("credit") or item.get("contribution")
            )

            corresponding_flag = item.get("corresponding")
            if corresponding_flag is None:
                corresponding_flag = item.get("corresponding_author")
            corresponding = self._coerce_bool(corresponding_flag)
            corresponding_note = self._coerce_string(
                item.get("corresponding_note")
                or item.get("correspondence")
                or item.get("correspondence_note")
            )
            if corresponding and not corresponding_note and email_value:
                corresponding_note = (
                    f"Corresponding author: {escape_latex_chars(email_value)}"
                )

            footnote_text = self._coerce_string(
                item.get("footnote") or item.get("note") or item.get("author_note")
            )

            short_name_value = self._coerce_string(
                item.get("short_name") or item.get("initials")
            )

            entry = {
                "name": escaped_name,
                "indices": indices,
                "indices_str": ",".join(indices),
                "email": escape_latex_chars(email_value) if email_value else None,
                "url": escape_latex_chars(url_value) if url_value else None,
                "orcid": escape_latex_chars(orcid_value) if orcid_value else None,
                "credit": escape_latex_chars(credit_value) if credit_value else None,
                "corr_mark": None,
                "footnote_mark": None,
                "short_name": escape_latex_chars(short_name_value)
                if short_name_value
                else escaped_name,
            }

            if corresponding and corresponding_note:
                mark = str(corr_counter)
                entry["corr_mark"] = mark
                correspondence_entries.append(
                    {"mark": mark, "text": escape_latex_chars(corresponding_note)}
                )
                corr_counter += 1

            if footnote_text:
                mark = str(footnote_counter)
                entry["footnote_mark"] = mark
                footnote_entries.append(
                    {"mark": mark, "text": escape_latex_chars(footnote_text)}
                )
                footnote_counter += 1

            author_entries.append(entry)

        affiliation_entries = [
            affiliation_registry[key]
            for key in affiliation_order
            if key in affiliation_registry
        ]

        return (
            author_entries,
            affiliation_entries,
            correspondence_entries,
            footnote_entries,
        )

    def _coerce_affiliation(self, payload: Any) -> tuple[str, dict[str, Any]]:
        if isinstance(payload, Mapping):
            fields: dict[str, str] = {}
            for key, value in payload.items():
                if key is None:
                    continue
                normalised_key = str(key).lower().replace("-", "_")
                if normalised_key not in self._AFFILIATION_FIELDS:
                    continue
                coerced = self._coerce_string(value)
                if not coerced:
                    continue
                fields[normalised_key] = escape_latex_chars(coerced)
            if not fields:
                text_value = self._coerce_string(
                    payload.get("text") or payload.get("value")
                )
                if text_value:
                    escaped = escape_latex_chars(text_value)
                    return (escaped, {"text": escaped})
            key = "|".join(f"{k}:{v}" for k, v in sorted(fields.items()))
            return (key, {"fields": fields})

        coerced = self._coerce_string(payload)
        if not coerced:
            return ("", {"text": ""})
        escaped = escape_latex_chars(coerced)
        return (escaped, {"text": escaped})

    def _render_affiliation(self, payload: Mapping[str, Any]) -> str:
        fields = payload.get("fields")
        if isinstance(fields, Mapping) and fields:
            parts: list[str] = []
            for key in (
                "organization",
                "institution",
                "department",
                "addressline",
                "city",
                "state",
                "province",
                "postcode",
                "postal_code",
                "country",
            ):
                value = fields.get(key)
                if value:
                    parts.append(f"{self._map_affiliation_key(key)}={{{value}}}")
            if parts:
                return ",\n            ".join(parts)

        text = payload.get("text")
        if isinstance(text, str) and text:
            return text
        return ""

    def _map_affiliation_key(self, key: str) -> str:
        mapping = {
            "institution": "organization",
            "postal_code": "postcode",
            "province": "state",
        }
        return mapping.get(key, key)

    def _iter_affiliations(self, payload: Any) -> Iterable[Any]:
        if payload is None:
            return []
        if isinstance(payload, (str, Mapping)):
            return [payload]
        if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            return list(payload)
        return [payload]

    def _coerce_string(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            candidate = value.strip()
        else:
            candidate = str(value).strip()
        return candidate or None

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


__all__ = ["Template"]
