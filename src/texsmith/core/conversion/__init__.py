"""Shared conversion primitives exposed by the core package."""

from __future__ import annotations

from .inputs import (
    DOCUMENT_SELECTOR_SENTINEL,
    InputKind,
    SlotOptions,
    UnsupportedInputError,
    coerce_slot_selector,
    extract_content,
    extract_front_matter_bibliography,
    extract_front_matter_slots,
    extract_front_matter_slots_with_options,
    parse_slot_mapping,
    parse_slot_mapping_with_options,
)
from .models import ConversionRequest, SlotAssignment


__all__ = [
    "DOCUMENT_SELECTOR_SENTINEL",
    "ConversionRequest",
    "InputKind",
    "SlotAssignment",
    "SlotOptions",
    "UnsupportedInputError",
    "coerce_slot_selector",
    "extract_content",
    "extract_front_matter_bibliography",
    "extract_front_matter_slots",
    "extract_front_matter_slots_with_options",
    "parse_slot_mapping",
    "parse_slot_mapping_with_options",
]
