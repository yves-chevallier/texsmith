"""Input parsing utilities shared across the conversion pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, FeatureNotFound

from ..conversion.debug import ConversionError
from ..conversion_contexts import DocumentContext
from ..metadata import PressMetadataError, normalise_press_metadata


DOCUMENT_SELECTOR_SENTINEL = "@document"


class UnsupportedInputError(Exception):
    """Raised when a CLI input argument cannot be processed."""


class InputKind(Enum):
    """Supported input modalities handled by the conversion pipeline."""

    MARKDOWN = "markdown"
    HTML = "html"


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


def build_document_context(
    *,
    name: str,
    source_path: Path,
    html: str,
    front_matter: Mapping[str, Any] | None,
    base_level: int,
    drop_title: bool,
    numbered: bool,
    title_from_heading: bool = False,
    extracted_title: str | None = None,
) -> DocumentContext:
    """Construct a document context enriched with metadata and slot requests."""
    metadata = dict(front_matter or {})
    try:
        press_payload = normalise_press_metadata(metadata)
    except PressMetadataError as exc:
        raise ConversionError(str(exc)) from exc
    metadata.setdefault("_source_dir", str(source_path.parent))
    metadata.setdefault("_source_path", str(source_path))
    if press_payload:
        press_payload.setdefault("_source_dir", str(source_path.parent))
        press_payload.setdefault("_source_path", str(source_path))
    slot_requests = extract_front_matter_slots(metadata)

    return DocumentContext(
        name=name,
        source_path=source_path,
        html=html,
        base_level=base_level,
        numbered=numbered,
        drop_title=drop_title,
        title_from_heading=title_from_heading,
        extracted_title=extracted_title,
        front_matter=metadata,
        slot_requests=slot_requests,
    )


def coerce_slot_selector(payload: Any) -> str | None:
    """Normalise a selector definition coming from front matter."""
    if isinstance(payload, str):
        candidate = payload.strip()
        return candidate or None
    if isinstance(payload, Mapping):
        for key in ("label", "title", "section"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def parse_slot_mapping(raw: Any) -> dict[str, str]:
    """Parse slot mappings declared in front matter structures."""
    overrides: dict[str, str] = {}
    if not raw:
        return overrides

    if isinstance(raw, Mapping):
        for slot_name, payload in raw.items():
            if not isinstance(slot_name, str):
                continue
            selector = coerce_slot_selector(payload)
            if selector:
                key = slot_name.strip()
                if key:
                    overrides[key] = selector
        return overrides

    if isinstance(raw, Iterable) and not isinstance(raw, str | bytes):
        for entry in raw:
            if not isinstance(entry, Mapping):
                continue
            slot_name = entry.get("target") or entry.get("slot")
            if not isinstance(slot_name, str):
                continue
            selector = entry.get("label") or entry.get("title") or entry.get("section")
            selector_value = coerce_slot_selector(selector)
            if not selector_value:
                selector_value = coerce_slot_selector(entry)
            slot_key = slot_name.strip()
            if slot_key and selector_value:
                overrides[slot_key] = selector_value
        return overrides

    if isinstance(raw, str):
        entry = raw.strip()
        if entry and ":" in entry:
            name, selector = entry.split(":", 1)
            name = name.strip()
            selector = selector.strip()
            if name and selector:
                overrides[name] = selector
        return overrides

    return overrides


def extract_front_matter_slots(front_matter: Mapping[str, Any]) -> dict[str, str]:
    """Collect slot overrides defined in document front matter."""
    overrides: dict[str, str] = {}

    root_slots = front_matter.get("slots") or front_matter.get("entrypoints")
    overrides.update(parse_slot_mapping(root_slots))

    return overrides


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


def extract_front_matter_bibliography(
    front_matter: Mapping[str, Any] | None,
) -> dict[str, InlineBibliographyEntry]:
    """Return inline bibliography entries declared in the document front matter."""
    if not isinstance(front_matter, Mapping):
        return {}

    bibliography: dict[str, InlineBibliographyEntry] = {}
    container = front_matter.get("bibliography")
    if isinstance(container, Mapping):
        for key, value in container.items():
            if not isinstance(key, str):
                continue
            entry = _parse_inline_bibliography_entry(key, value)
            bibliography[key] = entry

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


def extract_content(html: str, selector: str) -> str:
    """Extract and return the inner HTML for the first element matching selector."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")

    element = soup.select_one(selector)
    if element is None:
        raise ValueError(f"Unable to locate content using selector '{selector}'.")
    return element.decode_contents()


__all__ = [
    "DOCUMENT_SELECTOR_SENTINEL",
    "InlineBibliographyEntry",
    "InlineBibliographyValidationError",
    "InputKind",
    "UnsupportedInputError",
    "build_document_context",
    "coerce_slot_selector",
    "extract_content",
    "extract_front_matter_bibliography",
    "extract_front_matter_slots",
    "parse_slot_mapping",
]
