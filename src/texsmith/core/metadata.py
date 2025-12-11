"""Helpers for normalising common press metadata across inputs."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from datetime import date, datetime
from typing import Any
import warnings

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


__all__ = ["PressMetadataError", "normalise_press_metadata"]


class PressMetadataError(ValueError):
    """Raised when press metadata fields contain invalid values."""


class _AuthorEntry(BaseModel):
    """Validated representation of a press author entry."""

    model_config = ConfigDict(extra="ignore")

    name: str
    affiliation: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _coerce_name(cls, value: Any) -> str:
        if value is None:
            raise ValueError("Author name cannot be empty.")
        candidate = value if isinstance(value, str) else str(value)
        stripped = candidate.strip()
        if not stripped:
            raise ValueError("Author name cannot be empty.")
        return stripped

    @field_validator("affiliation", mode="before")
    @classmethod
    def _coerce_affiliation(cls, value: Any) -> str | None:
        if value is None:
            return None
        candidate = value if isinstance(value, str) else str(value)
        stripped = candidate.strip()
        return stripped or None


_SPECIAL_FIELDS = ("title", "subtitle", "date")
_ROOT_SKIP_KEYS = {"press", "slots", "entrypoints"}
_NESTED_ALIAS_MAP: dict[tuple[str, str], str] = {
    ("glossary", "style"): "glossary_style",
    ("cover", "color"): "covercolor",
    ("cover", "logo"): "logo",
    ("imprint", "thanks"): "imprint_thanks",
    ("imprint", "license"): "imprint_license",
    ("imprint", "copyright"): "imprint_copyright",
    ("override", "preamble"): "preamble",
    ("snippet", "width"): "width",
    ("snippet", "margin"): "margin",
    ("snippet", "dogear"): "dogear",
    ("snippet", "border"): "border",
    ("from", "name"): "from_name",
    ("from", "address"): "from_address",
    ("from", "city"): "from_location",
    ("from", "location"): "from_location",
    ("to", "name"): "to_name",
    ("to", "address"): "to_address",
    ("signature", "align"): "signature_align",
}
_DIRECT_ALIAS_MAP = {
    "ps": "postscript",
    "postscript": "postscript",
    "myref": "reference",
    "my_ref": "reference",
}


def normalise_press_metadata(metadata: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Ensure ``metadata['press']`` exists and contains canonical common fields."""
    press_section = metadata.get("press")
    press_payload: dict[str, Any] = (
        dict(press_section) if isinstance(press_section, Mapping) else {}
    )
    metadata["press"] = press_payload

    for field in _SPECIAL_FIELDS:
        _copy_common_string(metadata, press_payload, field)

    _normalise_press_authors(metadata, press_payload)
    _flatten_press_aliases(press_payload)
    _sync_root_and_press(metadata, press_payload)
    return press_payload


def _copy_common_string(
    metadata: Mapping[str, Any],
    press_payload: MutableMapping[str, Any],
    field: str,
) -> None:
    existing = _coerce_metadata_string(press_payload.get(field))
    root_value = _coerce_metadata_string(metadata.get(field))
    if root_value is not None:
        if existing is not None and existing != root_value:
            warnings.warn(
                f"Overriding press.{field} with root front matter value '{root_value}'.",
                stacklevel=2,
            )
        press_payload[field] = root_value
        metadata[field] = root_value
    elif existing is not None:
        press_payload[field] = existing
        metadata.setdefault(field, existing)
    elif field in press_payload:
        press_payload.pop(field, None)


def _coerce_metadata_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    candidate = str(value).strip()
    return candidate or None


def _normalise_press_authors(
    metadata: Mapping[str, Any],
    press_payload: MutableMapping[str, Any],
) -> None:
    sources: list[Any] = []

    if isinstance(press_payload, Mapping):
        # Prefer already normalised authors lists from press metadata and ignore
        # scalar author fields when a list is present to avoid duplicate entries.
        if press_payload.get("authors"):
            sources.append(press_payload["authors"])
        elif "author" in press_payload:
            sources.append(press_payload["author"])

    if not sources:
        if metadata.get("authors"):
            sources.append(metadata.get("authors"))
        if "author" in metadata:
            sources.append(metadata.get("author"))

    if not sources:
        press_payload.setdefault("authors", [])
        press_payload.pop("author", None)
        return

    entries: list[dict[str, str | None]] = []
    for source in sources:
        entries.extend(_flatten_author_entries(source))

    if not entries:
        press_payload.setdefault("authors", [])
        press_payload.pop("author", None)
        return

    # Remove stale scalar author values to keep press metadata canonical.
    press_payload.pop("author", None)

    normalized: list[dict[str, str | None]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for entry in entries:
        try:
            candidate = _AuthorEntry.model_validate(entry).model_dump()
        except ValidationError as exc:
            raise PressMetadataError(
                "Invalid author metadata. Provide names and optional affiliations."
            ) from exc
        key = (candidate.get("name"), candidate.get("affiliation"))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(candidate)

    press_payload["authors"] = normalized
    metadata["authors"] = normalized
    metadata.pop("author", None)


def _flatten_press_aliases(press_payload: MutableMapping[str, Any]) -> None:
    for (section, key), target in _NESTED_ALIAS_MAP.items():
        nested = press_payload.get(section)
        if not isinstance(nested, Mapping):
            continue
        if key not in nested:
            continue
        value = nested[key]
        press_payload[target] = value

    for source, target in _DIRECT_ALIAS_MAP.items():
        if source not in press_payload:
            continue
        press_payload[target] = press_payload[source]


def _sync_root_and_press(
    metadata: MutableMapping[str, Any],
    press_payload: MutableMapping[str, Any],
) -> None:
    for key, value in list(metadata.items()):
        if key in _ROOT_SKIP_KEYS or key.startswith("_"):
            continue
        if key not in press_payload and value is not None:
            press_payload[key] = value

    for key, value in press_payload.items():
        if key in _ROOT_SKIP_KEYS:
            continue
        if key.startswith("_"):
            continue
        metadata.setdefault(key, value)


def _flatten_author_entries(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, Mapping):
        return _validate_mapping_entry(payload)
    if isinstance(payload, str):
        return [{"name": payload}]
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        flattened: list[dict[str, Any]] = []
        for item in payload:
            flattened.extend(_flatten_author_entries(item))
        return flattened
    return [{"name": payload}]


def _validate_mapping_entry(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "name" in payload or "affiliation" in payload:
        return [dict(payload)]
    if "author" in payload:
        normalised = dict(payload)
        normalised.setdefault("name", normalised.get("author"))
        return [normalised]
    raise PressMetadataError("Author objects must declare at least a 'name' field.")
