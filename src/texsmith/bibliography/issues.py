"""Shared data structures for bibliography processing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class BibliographyIssue:
    """Represents a problem encountered while loading bibliography entries."""

    message: str
    key: str | None = None
    source: Path | None = None
