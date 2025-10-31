"""Parsing helpers for bibliography payloads."""

from __future__ import annotations

import io

from pybtex.database import BibliographyData, Entry, Person
from pybtex.database.input import bibtex
from pybtex.exceptions import PybtexError

from texsmith.core.conversion.inputs import InlineBibliographyEntry


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


def bibliography_data_from_inline_entry(
    key: str,
    entry: InlineBibliographyEntry,
) -> BibliographyData:
    """Create a BibliographyData instance from a manual inline entry."""
    if not entry.is_manual or not entry.entry_type:
        raise ValueError("Inline entry must define a manual type before conversion.")

    persons_payload = {
        role: [Person(name) for name in names] for role, names in entry.persons.items() if names
    }

    bib_entry = Entry(entry.entry_type, fields=dict(entry.fields), persons=persons_payload)
    return BibliographyData(entries={key: bib_entry})
