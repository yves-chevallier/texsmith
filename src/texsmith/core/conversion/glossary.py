"""Front-matter glossary (acronyms) parsing and merging.

The legacy syntax ``*[ABBR]: Long form`` defined at the bottom of a Markdown
document is preserved. This module additionally validates a structured
``glossary:`` section in the YAML front matter — supporting groups, an explicit
glossary style, and explicit acronym entries — and produces synthetic
``*[ABBR]: Long form`` lines that are appended to the Markdown body so that the
standard ``abbr`` extension can replace every occurrence in the text without a
second parser. The structured payload also flows separately into the LaTeX
template context so the glossary fragment can render one ``\\printglossary``
table per group.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class GlossaryValidationError(ValueError):
    """Raised when the front-matter ``glossary`` section is invalid."""


class GlossaryEntryModel(BaseModel):
    """A single acronym definition declared in the front matter."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)
    group: str | None = None
    long: str | None = None

    @field_validator("description", "group", "long", mode="before")
    @classmethod
    def _strip_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class GlossaryGroupModel(BaseModel):
    """A glossary group (table) shown in the backmatter."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class GlossaryFrontMatterModel(BaseModel):
    """Validated representation of the ``glossary:`` front-matter section."""

    model_config = ConfigDict(extra="forbid")

    style: str = "long"
    groups: dict[str, GlossaryGroupModel] = Field(default_factory=dict)
    entries: dict[str, GlossaryEntryModel] = Field(default_factory=dict)

    @field_validator("style", mode="before")
    @classmethod
    def _strip_style(cls, value: Any) -> Any:
        if value is None:
            return "long"
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or "long"
        return value


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    """Resolved glossary entry exposed to the conversion pipeline."""

    key: str
    description: str
    group: str | None = None
    long: str | None = None


@dataclass(frozen=True, slots=True)
class GlossaryGroup:
    """Resolved glossary group exposed to the conversion pipeline."""

    key: str
    title: str


@dataclass(slots=True)
class GlossaryFrontMatter:
    """Aggregated front-matter glossary data ready for downstream consumers."""

    style: str = "long"
    groups: list[GlossaryGroup] = field(default_factory=list)
    entries: list[GlossaryEntry] = field(default_factory=list)

    @property
    def has_entries(self) -> bool:
        return bool(self.entries)

    def synthetic_abbr_lines(self) -> list[str]:
        """Return synthetic ``*[KEY]: description`` lines for the abbr extension."""
        lines: list[str] = []
        for entry in self.entries:
            description = entry.long or entry.description
            description = " ".join(description.split())
            if not description:
                continue
            lines.append(f"*[{entry.key}]: {description}")
        return lines


def _coerce_entry(key: str, value: Any) -> GlossaryEntryModel:
    if isinstance(value, str):
        return GlossaryEntryModel(description=value)
    if isinstance(value, Mapping):
        return GlossaryEntryModel(**dict(value))
    raise GlossaryValidationError(
        f"Glossary entry '{key}' must be a string or a mapping, got {type(value).__name__}."
    )


def _coerce_group(key: str, value: Any) -> GlossaryGroupModel:
    if isinstance(value, str):
        return GlossaryGroupModel(title=value)
    if isinstance(value, Mapping):
        return GlossaryGroupModel(**dict(value))
    raise GlossaryValidationError(
        f"Glossary group '{key}' must be a string title or a mapping, got {type(value).__name__}."
    )


def parse_front_matter_glossary(front_matter: Mapping[str, Any] | None) -> GlossaryFrontMatter | None:
    """Validate and normalise the ``glossary:`` front-matter section."""
    if not isinstance(front_matter, Mapping):
        return None

    raw = front_matter.get("glossary")
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, str):
        # Legacy form ``glossary: <style>`` keeps its meaning.
        style = raw.strip() or "long"
        return GlossaryFrontMatter(style=style)
    if not isinstance(raw, Mapping):
        raise GlossaryValidationError(
            "Front-matter 'glossary' must be a mapping when provided as an object."
        )

    raw_groups = raw.get("groups") or {}
    raw_entries = raw.get("entries") or {}

    if not isinstance(raw_groups, Mapping):
        raise GlossaryValidationError("'glossary.groups' must be a mapping of group_id -> title.")
    if not isinstance(raw_entries, Mapping):
        raise GlossaryValidationError(
            "'glossary.entries' must be a mapping of acronym -> description/options."
        )

    groups_payload = {str(key): _coerce_group(str(key), value) for key, value in raw_groups.items()}
    entries_payload = {
        str(key): _coerce_entry(str(key), value) for key, value in raw_entries.items()
    }

    payload = {
        "style": raw.get("style", "long"),
        "groups": groups_payload,
        "entries": entries_payload,
    }
    try:
        model = GlossaryFrontMatterModel(**payload)
    except ValidationError as exc:
        raise GlossaryValidationError(f"Invalid 'glossary' front matter: {exc}") from exc

    groups = [GlossaryGroup(key=key, title=group.title) for key, group in model.groups.items()]
    valid_group_keys = {group.key for group in groups}

    entries: list[GlossaryEntry] = []
    for raw_key, entry in model.entries.items():
        key = raw_key.strip()
        if not key:
            raise GlossaryValidationError(
                "Glossary entries must use a non-empty acronym as their key."
            )
        if entry.group is not None and entry.group not in valid_group_keys:
            raise GlossaryValidationError(
                f"Glossary entry '{key}' references unknown group '{entry.group}'."
            )
        entries.append(
            GlossaryEntry(
                key=key,
                description=entry.description,
                group=entry.group,
                long=entry.long,
            )
        )

    return GlossaryFrontMatter(style=model.style, groups=groups, entries=entries)


def append_synthetic_abbr_lines(markdown_body: str, glossary: GlossaryFrontMatter) -> str:
    """Append synthetic ``*[KEY]: description`` lines to a Markdown body."""
    lines = glossary.synthetic_abbr_lines()
    if not lines:
        return markdown_body

    suffix = "\n".join(lines)
    if not markdown_body:
        return suffix + "\n"
    if markdown_body.endswith("\n\n"):
        return markdown_body + suffix + "\n"
    if markdown_body.endswith("\n"):
        return markdown_body + "\n" + suffix + "\n"
    return markdown_body + "\n\n" + suffix + "\n"


__all__ = [
    "GlossaryEntry",
    "GlossaryEntryModel",
    "GlossaryFrontMatter",
    "GlossaryFrontMatterModel",
    "GlossaryGroup",
    "GlossaryGroupModel",
    "GlossaryValidationError",
    "append_synthetic_abbr_lines",
    "parse_front_matter_glossary",
]
