"""Inline bibliography entries declared in a document's front matter.

``press.sources.bibliography`` maps a citation key to either a DOI (a string,
or a mapping carrying one) or a complete entry typed by its ``type``. This
module parses and validates that mapping; :mod:`texsmith.core.bibliography.loading`
turns the result into a ``.bib``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
import re
from typing import Any


__all__ = [
    "InlineBibliographyEntry",
    "InlineBibliographyValidationError",
    "extract_front_matter_bibliography",
]


class InlineBibliographyValidationError(ValueError):
    """Raised when inline bibliography entries contain invalid data."""


@dataclass(slots=True)
class InlineBibliographyEntry:
    """Validated representation of a front-matter bibliography entry."""

    key: str
    doi: str | None = None
    entry_type: str | None = None
    fields: dict[str, str] = field(default_factory=dict)
    persons: dict[str, list[str]] = field(default_factory=dict)

    @property
    def is_manual(self) -> bool:
        """Return True when the entry embeds explicit bibliographic fields."""
        return self.entry_type is not None


_ISO_YEAR_RE = re.compile(r"^(?P<year>\d{4})$")
_ISO_YEAR_MONTH_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})$")
_ISO_DATE_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$")

_COMMON_ALLOWED_FIELDS = {
    "title",
    "subtitle",
    "date",
    "year",
    "month",
    "day",
    "note",
    "url",
    "doi",
}
_MISC_ALLOWED_FIELDS = _COMMON_ALLOWED_FIELDS | {"howpublished", "publisher", "address"}
_ARTICLE_ALLOWED_FIELDS = _COMMON_ALLOWED_FIELDS | {
    "journal",
    "volume",
    "number",
    "pages",
    "publisher",
    "address",
    "issn",
}
_BOOK_ALLOWED_FIELDS = _COMMON_ALLOWED_FIELDS | {
    "publisher",
    "address",
    "edition",
    "series",
    "volume",
    "number",
    "pages",
    "isbn",
}
_INLINE_BIBLIOGRAPHY_SCHEMAS: dict[str, dict[str, set[str]]] = {
    "misc": {
        "required": {"title"},
        "allowed": _MISC_ALLOWED_FIELDS,
    },
    "article": {
        "required": {"title", "journal"},
        "allowed": _ARTICLE_ALLOWED_FIELDS,
    },
    "book": {
        "required": {"title", "publisher"},
        "allowed": _BOOK_ALLOWED_FIELDS,
    },
}
_PERSON_KEYS = {"author", "authors"}
_RESERVED_KEYS = {"type", *(_PERSON_KEYS)}


#: Where a document declares its inline bibliography, most canonical first.
#: ``press.sources.bibliography`` is the documented spelling;
#: ``normalise_press_metadata`` also flattens it to ``sources.bibliography``.
#: A bare ``bibliography`` at the root is the deprecated spelling — tmark
#: relocates it and emits ``deprecated-frontmatter-key`` itself, so reading it
#: here needs no second diagnostic.
_BIBLIOGRAPHY_PATHS = (
    ("press", "sources", "bibliography"),
    ("sources", "bibliography"),
    ("bibliography",),
)


def _bibliography_container(front_matter: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for path in _BIBLIOGRAPHY_PATHS:
        cursor: Any = front_matter
        for key in path:
            if not isinstance(cursor, Mapping):
                cursor = None
                break
            cursor = cursor.get(key)
        if isinstance(cursor, Mapping) and cursor:
            return cursor
    return None


def extract_front_matter_bibliography(
    front_matter: Mapping[str, Any] | None,
) -> dict[str, InlineBibliographyEntry]:
    """Return inline bibliography entries declared in the document front matter."""
    if not isinstance(front_matter, Mapping):
        return {}

    container = _bibliography_container(front_matter)
    if container is None:
        return {}

    bibliography: dict[str, InlineBibliographyEntry] = {}
    for key, value in container.items():
        if not isinstance(key, str):
            continue
        bibliography[key] = _parse_inline_bibliography_entry(key, value)

    return bibliography


def _parse_inline_bibliography_entry(key: str, value: Any) -> InlineBibliographyEntry:
    if isinstance(value, str):
        doi = _coerce_bibliography_doi(value)
        if not doi:
            raise InlineBibliographyValidationError(
                f"Bibliography entry '{key}' must not be empty."
            )
        return InlineBibliographyEntry(key=key, doi=doi)

    if isinstance(value, Mapping):
        if "type" in value:
            return _parse_manual_bibliography_mapping(key, value)
        doi = _coerce_bibliography_doi(value)
        if not doi:
            raise InlineBibliographyValidationError(
                f"Bibliography entry '{key}' must define a DOI or a 'type'."
            )
        return InlineBibliographyEntry(key=key, doi=doi)

    raise InlineBibliographyValidationError(
        f"Bibliography entry '{key}' must be a string DOI or a mapping of fields."
    )


def _parse_manual_bibliography_mapping(
    key: str,
    payload: Mapping[str, Any],
) -> InlineBibliographyEntry:
    raw_type = payload.get("type")
    if not isinstance(raw_type, str) or not raw_type.strip():
        raise InlineBibliographyValidationError(
            f"Bibliography entry '{key}' must define a textual 'type'."
        )

    entry_type = raw_type.strip().lower()
    schema = _INLINE_BIBLIOGRAPHY_SCHEMAS.get(entry_type)
    if schema is None:
        allowed = ", ".join(sorted(_INLINE_BIBLIOGRAPHY_SCHEMAS))
        raise InlineBibliographyValidationError(
            f"Bibliography entry '{key}' declares unsupported type '{entry_type}'. "
            f"Allowed types: {allowed}."
        )

    allowed_fields = schema["allowed"]
    required_fields = schema["required"]

    invalid_fields = sorted(
        field_name
        for field_name in payload
        if field_name not in allowed_fields and field_name not in _RESERVED_KEYS
    )
    if invalid_fields:
        raise InlineBibliographyValidationError(
            f"Bibliography entry '{key}' ({entry_type}) contains unsupported field(s): "
            + ", ".join(invalid_fields)
            + "."
        )

    persons: dict[str, list[str]] = {}
    author_values: list[str] = []
    if "author" in payload:
        author_values.extend(_coerce_person_list(key, "author", payload.get("author")))
    if "authors" in payload:
        author_values.extend(_coerce_person_list(key, "authors", payload.get("authors")))
    if author_values:
        persons["author"] = author_values

    fields: dict[str, str] = {}
    for field_name, raw_value in payload.items():
        if field_name in _RESERVED_KEYS:
            continue
        if field_name == "date":
            date_value = _coerce_bibliography_field_value(key, field_name, raw_value)
            if date_value:
                fields["date"] = date_value
                derived = _derive_date_components(key, date_value)
                for derived_name, derived_value in derived.items():
                    fields.setdefault(derived_name, derived_value)
            continue

        field_value = _coerce_bibliography_field_value(key, field_name, raw_value)
        if field_value is not None:
            fields[field_name] = field_value

    for required in required_fields:
        if required not in fields or not fields[required]:
            raise InlineBibliographyValidationError(
                f"Bibliography entry '{key}' ({entry_type}) is missing required field '{required}'."
            )

    return InlineBibliographyEntry(
        key=key,
        entry_type=entry_type,
        fields=fields,
        persons=persons,
    )


def _coerce_bibliography_doi(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, Mapping):
        candidate = value.get("doi")
        if isinstance(candidate, str):
            stripped = candidate.strip()
            if stripped:
                return stripped
    return None


def _coerce_person_list(
    key: str,
    field: str,
    value: Any,
) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            raise InlineBibliographyValidationError(
                f"Bibliography entry '{key}' field '{field}' must not be empty."
            )
        return [candidate]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        result: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise InlineBibliographyValidationError(
                    f"Bibliography entry '{key}' field '{field}' must contain only strings."
                )
            candidate = item.strip()
            if not candidate:
                raise InlineBibliographyValidationError(
                    f"Bibliography entry '{key}' field '{field}' contains an empty value."
                )
            result.append(candidate)
        if not result:
            raise InlineBibliographyValidationError(
                f"Bibliography entry '{key}' field '{field}' must define at least one value."
            )
        return result
    raise InlineBibliographyValidationError(
        f"Bibliography entry '{key}' field '{field}' must be a string or list of strings."
    )


def _coerce_bibliography_field_value(key: str, field: str, value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not value.is_integer():
            raise InlineBibliographyValidationError(
                f"Bibliography entry '{key}' field '{field}' must be an integer when numeric."
            )
        return str(int(value))
    raise InlineBibliographyValidationError(
        f"Bibliography entry '{key}' field '{field}' must be a string or integer."
    )


def _derive_date_components(key: str, value: str) -> dict[str, str]:
    candidate = value.strip()
    if not candidate:
        return {}

    match = _ISO_DATE_RE.match(candidate)
    if match:
        year = match.group("year")
        month = match.group("month")
        day = match.group("day")
        _validate_month(key, month)
        _validate_day(key, day)
        return {"year": year, "month": month, "day": day}

    match = _ISO_YEAR_MONTH_RE.match(candidate)
    if match:
        year = match.group("year")
        month = match.group("month")
        _validate_month(key, month)
        return {"year": year, "month": month}

    match = _ISO_YEAR_RE.match(candidate)
    if match:
        return {"year": match.group("year")}

    raise InlineBibliographyValidationError(
        f"Bibliography entry '{key}' field 'date' must follow ISO formats YYYY, YYYY-MM, or YYYY-MM-DD."
    )


def _validate_month(key: str, value: str) -> None:
    month_int = int(value)
    if not 1 <= month_int <= 12:
        raise InlineBibliographyValidationError(
            f"Bibliography entry '{key}' field 'date' contains an invalid month '{value}'."
        )


def _validate_day(key: str, value: str) -> None:
    day_int = int(value)
    if not 1 <= day_int <= 31:
        raise InlineBibliographyValidationError(
            f"Bibliography entry '{key}' field 'date' contains an invalid day '{value}'."
        )
