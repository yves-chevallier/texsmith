"""Shared constants for font handling."""

from __future__ import annotations


SCRIPT_FALLBACK_ALIASES: dict[str, str] = {
    "greek": "latin-greek-cyrillic",
    "cyrillic": "latin-greek-cyrillic",
}


__all__ = ["SCRIPT_FALLBACK_ALIASES"]
