"""Parsing helpers for bibliography payloads."""

from __future__ import annotations

import io

from pybtex.database import BibliographyData
from pybtex.database.input import bibtex
from pybtex.exceptions import PybtexError


def bibliography_data_from_string(payload: str, key: str) -> BibliographyData:
    """Parse a BibTeX payload and scope it to a specific reference key."""
    parser = bibtex.Parser()
    try:
        parsed = parser.parse_stream(io.StringIO(payload))
    except (OSError, PybtexError) as exc:
        raise PybtexError(f"Failed to parse inline bibliography payload: {exc}") from exc

    entries = list(parsed.entries.items())
    if not entries:
        raise PybtexError("Inline bibliography payload does not contain an entry.")
    if len(entries) > 1:
        raise PybtexError("Inline bibliography payload must contain a single entry.")

    _, entry = entries[0]
    return BibliographyData(entries={key: entry})

