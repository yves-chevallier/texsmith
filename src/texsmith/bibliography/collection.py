"""Aggregation utilities for BibTeX references."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from pybtex.database import BibliographyData, Entry, Person
from pybtex.database.input import bibtex
from pybtex.exceptions import PybtexError

from .issues import BibliographyIssue


class BibliographyCollection:
    """Aggregate references from one or more BibTeX sources."""

    def __init__(self) -> None:
        self._entries: dict[str, Entry] = {}
        self._sources: dict[str, set[Path]] = {}
        self._issues: list[BibliographyIssue] = []
        self._file_entry_counts: dict[Path, int] = {}
        self._file_order: list[Path] = []

    @property
    def issues(self) -> Sequence[BibliographyIssue]:
        """Return the list of issues discovered while loading references."""
        return tuple(self._issues)

    @property
    def file_stats(self) -> Sequence[tuple[Path, int]]:
        """Return (file, entry_count) pairs in the order files were processed."""
        return tuple((path, self._file_entry_counts.get(path, 0)) for path in self._file_order)

    def load_files(self, files: Iterable[Path | str]) -> None:
        """Load BibTeX entries from one or more files."""
        for file_path in files:
            self._load_file(Path(file_path))

    def _load_file(self, file_path: Path) -> None:
        file_path = file_path.resolve()
        self._file_order.append(file_path)
        parser = bibtex.Parser()

        try:
            data = parser.parse_file(str(file_path))
        except (OSError, PybtexError) as exc:
            self._issues.append(
                BibliographyIssue(
                    message=f"Failed to parse '{file_path}': {exc}",
                    key=None,
                    source=file_path,
                )
            )
            self._file_entry_counts[file_path] = 0
            return

        entry_count = len(data.entries)
        self._file_entry_counts[file_path] = entry_count
        if entry_count == 0:
            self._issues.append(
                BibliographyIssue(
                    message="No references found in file.",
                    key=None,
                    source=file_path,
                )
            )

        self._merge_entries(data, file_path)

    def load_data(
        self,
        data: BibliographyData,
        *,
        source: Path | str | None = None,
    ) -> None:
        """Merge pre-parsed bibliography data into the collection."""
        source_path = self._resolve_source_path(source)
        entry_count = len(data.entries)
        self._file_entry_counts[source_path] = (
            self._file_entry_counts.get(source_path, 0) + entry_count
        )
        if source_path not in self._file_order:
            self._file_order.append(source_path)

        if entry_count == 0:
            self._issues.append(
                BibliographyIssue(
                    message="No references found in inline bibliography data.",
                    key=None,
                    source=source_path,
                )
            )
            return

        self._merge_entries(data, source_path)

    def _resolve_source_path(self, source: Path | str | None) -> Path:
        if source is None:
            return Path("inline-bibliography.bib")
        if isinstance(source, Path):
            return source
        return Path(source)

    def _merge_entries(self, data: BibliographyData, source: Path) -> None:
        for key, entry in data.entries.items():
            existing = self._entries.get(key)

            if existing is None:
                self._entries[key] = entry
                self._sources[key] = {source}
                continue

            if not self._entries_equivalent(existing, entry):
                self._issues.append(
                    BibliographyIssue(
                        message=(
                            "Duplicate entry conflicts with an existing "
                            "reference; ignoring the newer definition."
                        ),
                        key=key,
                        source=source,
                    )
                )
                self._sources[key].add(source)
                continue

            # Matching duplicates still originate from multiple sources.
            self._sources[key].add(source)

    def find(self, reference_key: str) -> dict[str, Any] | None:
        """Return the portable representation of a specific reference."""
        entry = self._entries.get(reference_key)
        if entry is None:
            return None

        return self._portable_entry(reference_key, entry, self._sources[reference_key])

    def list_references(self) -> list[dict[str, Any]]:
        """Return all references as portable dictionaries sorted by key."""
        portable: list[dict[str, Any]] = []
        for key in sorted(self._entries):
            portable.append(self._portable_entry(key, self._entries[key], self._sources[key]))
        return portable

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Return a dictionary keyed by reference identifiers."""
        return {
            key: self._portable_entry(key, entry, self._sources[key])
            for key, entry in self._entries.items()
        }

    def to_bibliography_data(self, *, keys: Iterable[str] | None = None) -> BibliographyData:
        """Return a BibliographyData object scoped to the selected keys."""
        if keys is None:
            entries = dict(self._entries)
        else:
            selected = {key for key in keys if key in self._entries}
            entries = {key: self._entries[key] for key in selected}
        return BibliographyData(entries=entries)

    def write_bibtex(self, target: Path | str, *, keys: Iterable[str] | None = None) -> None:
        """Persist the bibliography to a BibTeX file."""
        path = Path(target)
        data = self.to_bibliography_data(keys=keys)
        data.to_file(str(path))

    def _entries_equivalent(self, first: Entry, second: Entry) -> bool:
        return self._entry_signature(first) == self._entry_signature(second)

    def _entry_signature(self, entry: Entry) -> dict[str, Any]:
        return {
            "type": entry.type,
            "fields": dict(entry.fields),
            "persons": {
                role: [self._person_signature(person) for person in persons]
                for role, persons in sorted(entry.persons.items())
            },
        }

    def _portable_entry(self, key: str, entry: Entry, sources: set[Path]) -> dict[str, Any]:
        return {
            "key": key,
            "type": entry.type,
            "fields": dict(entry.fields),
            "persons": {
                role: [self._person_payload(person) for person in persons]
                for role, persons in sorted(entry.persons.items())
            },
            "source_files": sorted(str(path) for path in sources),
        }

    def _person_signature(self, person: Person) -> tuple[tuple[str, ...], ...]:
        signature: list[tuple[str, ...]] = []
        for attribute in (
            "first_names",
            "middle_names",
            "prelast_names",
            "last_names",
            "lineage_names",
        ):
            value = getattr(person, attribute, ())
            signature.append(tuple(str(part) for part in value))
        return tuple(signature)

    def _person_payload(self, person: Person) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for attribute, key in (
            ("first_names", "first"),
            ("middle_names", "middle"),
            ("prelast_names", "prelast"),
            ("last_names", "last"),
            ("lineage_names", "lineage"),
        ):
            value = getattr(person, attribute, ())
            payload[key] = [str(part) for part in value]

        payload["text"] = str(person)
        return payload

