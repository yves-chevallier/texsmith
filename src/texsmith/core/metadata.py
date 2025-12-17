"""Helpers for normalising common press metadata across inputs."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
import copy
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
    """Flatten press metadata into the root mapping while preserving compatibility."""
    press_section = metadata.pop("press", None)
    press_payload: dict[str, Any] = (
        dict(press_section) if isinstance(press_section, Mapping) else {}
    )

    root_payload = dict(metadata)
    _hoist_dotted_press_keys(root_payload, press_payload)

    merged = _merge_press_overrides(press_payload, root_payload)
    _coerce_common_strings(merged, press_payload)
    _normalise_press_authors(merged)
    _flatten_press_aliases(merged)

    metadata.clear()
    metadata.update(merged)

    press_view = _build_press_view(merged)
    if press_view:
        metadata["press"] = press_view

    return press_view


def _merge_press_overrides(
    press_payload: Mapping[str, Any], root_payload: Mapping[str, Any]
) -> dict[str, Any]:
    merged: dict[str, Any] = copy.deepcopy(press_payload)

    def _merge(target: MutableMapping[str, Any], source: Mapping[str, Any]) -> None:
        for key, value in source.items():
            existing = target.get(key)
            if isinstance(existing, MutableMapping) and isinstance(value, Mapping):
                nested: dict[str, Any] = dict(existing)
                _merge(nested, value)
                target[key] = nested
                continue
            target[key] = copy.deepcopy(value)

    _merge(merged, root_payload)
    return merged


def _coerce_common_strings(
    merged: MutableMapping[str, Any], press_payload: Mapping[str, Any]
) -> None:
    for field in _SPECIAL_FIELDS:
        existing = _coerce_metadata_string(merged.get(field))
        source = _coerce_metadata_string(press_payload.get(field))
        if existing is None and source is not None:
            merged[field] = source
        elif existing is not None:
            if source is not None and source != existing:
                warnings.warn(
                    f"Overriding press.{field} with root front matter value '{existing}'.",
                    stacklevel=2,
                )
            merged[field] = existing


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


def _normalise_press_authors(metadata: MutableMapping[str, Any]) -> None:
    sources: list[Any] = []

    authors_present = "authors" in metadata
    author_present = "author" in metadata

    if authors_present:
        sources.append(metadata.get("authors"))
    if author_present:
        sources.append(metadata.get("author"))

    if not sources:
        if authors_present:
            metadata["authors"] = []
        if author_present:
            metadata.pop("author", None)
        return

    entries: list[dict[str, str | None]] = []
    for source in sources:
        entries.extend(_flatten_author_entries(source))

    if not entries:
        metadata.setdefault("authors", [])
        metadata.pop("author", None)
        return

    # Remove stale scalar author values to keep press metadata canonical.
    metadata.pop("author", None)

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

    metadata["authors"] = normalized


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


def _hoist_dotted_press_keys(
    root_payload: MutableMapping[str, Any], press_payload: MutableMapping[str, Any]
) -> None:
    dotted_keys = [
        key
        for key in list(root_payload.keys())
        if isinstance(key, str) and key.startswith("press.")
    ]
    for dotted in dotted_keys:
        value = root_payload.pop(dotted)
        segments = [segment for segment in dotted.split(".")[1:] if segment]
        if not segments:
            continue
        target = press_payload
        for segment in segments[:-1]:
            existing = target.get(segment)
            nested = dict(existing) if isinstance(existing, MutableMapping) else {}
            target[segment] = nested
            target = nested
        target[segments[-1]] = value

    slash_keys = [
        key
        for key in list(root_payload.keys())
        if isinstance(key, str) and key.startswith("press/")
    ]
    for entry in slash_keys:
        value = root_payload.pop(entry)
        suffix = entry.split("/", 1)[1]
        if suffix:
            press_payload[suffix] = value


def _build_press_view(merged: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in merged.items()
        if key not in _ROOT_SKIP_KEYS and not str(key).startswith("_")
    }


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
