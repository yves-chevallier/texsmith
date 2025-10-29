"""Input parsing utilities shared across the conversion pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import Enum
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, FeatureNotFound

from ..conversion_contexts import DocumentContext


DOCUMENT_SELECTOR_SENTINEL = "@document"


class UnsupportedInputError(Exception):
    """Raised when a CLI input argument cannot be processed."""


class InputKind(Enum):
    """Supported input modalities handled by the conversion pipeline."""

    MARKDOWN = "markdown"
    HTML = "html"


def build_document_context(
    *,
    name: str,
    source_path: Path,
    html: str,
    front_matter: Mapping[str, Any] | None,
    base_level: int,
    heading_level: int,
    drop_title: bool,
    numbered: bool,
    title_from_heading: bool = False,
    extracted_title: str | None = None,
) -> DocumentContext:
    """Construct a document context enriched with metadata and slot requests."""
    metadata = dict(front_matter or {})
    slot_requests = extract_front_matter_slots(metadata)

    return DocumentContext(
        name=name,
        source_path=source_path,
        html=html,
        base_level=base_level,
        heading_level=heading_level,
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

    press_section = front_matter.get("press")
    if isinstance(press_section, Mapping):
        meta_slots = press_section.get("slots") or press_section.get("entrypoints")
        overrides.update(parse_slot_mapping(meta_slots))

    root_slots = front_matter.get("slots") or front_matter.get("entrypoints")
    overrides.update(parse_slot_mapping(root_slots))

    return overrides


def extract_front_matter_bibliography(front_matter: Mapping[str, Any] | None) -> dict[str, str]:
    """Return DOI mappings declared in the document front matter."""
    if not isinstance(front_matter, Mapping):
        return {}

    bibliography: dict[str, str] = {}
    containers: list[Any] = []
    press_section = front_matter.get("press")
    if isinstance(press_section, Mapping):
        containers.append(press_section.get("bibliography"))
    containers.append(front_matter.get("bibliography"))

    for candidate in containers:
        if not isinstance(candidate, Mapping):
            continue
        for key, value in candidate.items():
            if not isinstance(key, str):
                continue
            doi = _coerce_bibliography_doi(value)
            if not doi:
                continue
            bibliography[key] = doi

    return bibliography


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
    "InputKind",
    "UnsupportedInputError",
    "build_document_context",
    "coerce_slot_selector",
    "extract_content",
    "extract_front_matter_bibliography",
    "extract_front_matter_slots",
    "parse_slot_mapping",
]
