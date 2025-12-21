"""Shared conversion primitives exposed by the core package."""

from __future__ import annotations

from .inputs import (
    DOCUMENT_SELECTOR_SENTINEL,
    InputKind,
    UnsupportedInputError,
    build_document_context,
    coerce_slot_selector,
    extract_content,
    extract_front_matter_bibliography,
    extract_front_matter_slots,
    parse_slot_mapping,
)
from .models import ConversionRequest, ConversionSettings, SlotAssignment


__all__ = [
    "DOCUMENT_SELECTOR_SENTINEL",
    "ConversionRequest",
    "ConversionSettings",
    "InputKind",
    "SlotAssignment",
    "UnsupportedInputError",
    "build_document_context",
    "coerce_slot_selector",
    "extract_content",
    "extract_front_matter_bibliography",
    "extract_front_matter_slots",
    "parse_slot_mapping",
]
