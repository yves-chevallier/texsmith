# ruff: noqa: TRY004
# Pydantic v2 ``mode="before"`` field validators must raise ``ValueError`` (or
# ``AssertionError``/``PydanticCustomError``) for the framework to wrap them
# in ``ValidationError``; ``TypeError`` propagates raw and bypasses the
# error-aggregation we depend on in ``_parse``. The TRY004 lint rule prefers
# ``TypeError`` for type checks but is at odds with that contract here.
"""Resolve the document ``version`` front-matter into canonical text.

The front-matter ``version`` field accepts four shapes:

- a free-form string (``version: "Consolidation du draft"``) — returned trimmed;
- a list of non-negative integers (``version: [2, 3, 0]``) — joined with dots
  to form a semver-style label (``"2.3.0"``);
- a mapping with explicit semver fields
  (``version: {major: 2, minor: 3, patch: 0, pre: rc1, build: abc}``) —
  rendered as ``"<major>.<minor>.<patch>[-<pre>][+<build>]``;
- a mapping that requests git derivation (``version: {git: true,
  suffix: "draft"}``) — replaced with ``git describe --tags --dirty`` (with a
  short-hash fallback) and optionally appended with ``suffix``.

The literal string ``"git"`` (case-insensitive) is preserved as a shorthand for
``{git: true}``.

Each shape is validated by Pydantic, so unknown keys, missing fields, or wrong
types raise :class:`DocumentVersionError` with a clear message instead of
silently dropping data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from texsmith.core import git_version


__all__ = [
    "DocumentVersionError",
    "FreeFormVersion",
    "GitVersion",
    "SemverDictVersion",
    "SemverListVersion",
    "VersionSpec",
    "format_version",
]


class DocumentVersionError(ValueError):
    """Raised when the front-matter ``version`` value is malformed."""


class _BaseSpec(BaseModel):
    """Base class for the four version-spec shapes."""

    model_config = ConfigDict(extra="forbid")

    def render(self, *, cwd: Path | None = None) -> str:
        """Return the canonical text rendering of this spec."""
        raise NotImplementedError  # pragma: no cover - abstract


class FreeFormVersion(_BaseSpec):
    """Free-form version label (``version: "Draft 3"``)."""

    text: str

    @field_validator("text", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("text must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be empty")
        return stripped

    def render(self, *, cwd: Path | None = None) -> str:
        return self.text


class SemverListVersion(_BaseSpec):
    """List-of-integers semver shorthand (``version: [2, 3, 0]``)."""

    parts: list[int] = Field(min_length=1)

    @field_validator("parts", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> list[int]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise ValueError("parts must be a list of non-negative integers")
        coerced: list[int] = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, int):
                raise ValueError(f"parts entry {item!r} must be a non-negative integer")
            if item < 0:
                raise ValueError(f"parts entry {item} must be non-negative")
            coerced.append(item)
        if not coerced:
            raise ValueError("parts must not be empty")
        return coerced

    def render(self, *, cwd: Path | None = None) -> str:
        return ".".join(str(part) for part in self.parts)


class SemverDictVersion(_BaseSpec):
    """Explicit semver mapping (``version: {major: 2, minor: 3, patch: 0}``)."""

    major: int
    minor: int
    patch: int
    pre: str | None = None
    build: str | None = None

    @field_validator("major", "minor", "patch", mode="before")
    @classmethod
    def _coerce_int(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("semver components must be non-negative integers")
        if value < 0:
            raise ValueError("semver components must be non-negative")
        return value

    @field_validator("pre", "build", mode="before")
    @classmethod
    def _coerce_label(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("pre/build labels must be strings")
        stripped = value.strip()
        return stripped or None

    def render(self, *, cwd: Path | None = None) -> str:
        core = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            core = f"{core}-{self.pre}"
        if self.build:
            core = f"{core}+{self.build}"
        return core


class GitVersion(_BaseSpec):
    """Git-derived version (``version: {git: true, suffix: "..."}``)."""

    git: bool
    suffix: str | None = None

    @field_validator("git", mode="before")
    @classmethod
    def _require_truthy(cls, value: Any) -> bool:
        if value is not True:
            raise ValueError("git must be true to request git-derived versions")
        return True

    @field_validator("suffix", mode="before")
    @classmethod
    def _coerce_suffix(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("suffix must be a string")
        stripped = value.strip()
        return stripped or None

    def render(self, *, cwd: Path | None = None) -> str:
        described = git_version.git_describe(cwd=cwd)
        if self.suffix and described:
            return f"{described} {self.suffix}"
        if self.suffix:
            return self.suffix
        return described


VersionSpec = FreeFormVersion | SemverListVersion | SemverDictVersion | GitVersion


def format_version(value: Any, *, cwd: Path | None = None) -> str:
    """Validate ``value`` against the version schema and render it as text.

    Returns ``""`` when ``value`` is ``None`` or an empty/whitespace string.
    Raises :class:`DocumentVersionError` for malformed structured shapes; the
    error preserves the underlying Pydantic message so users can self-correct.
    """
    spec = _parse(value)
    if spec is None:
        return ""
    return spec.render(cwd=cwd)


def _parse(value: Any) -> VersionSpec | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.lower() == "git":
            return GitVersion(git=True)
        return FreeFormVersion(text=text)
    if isinstance(value, Mapping):
        payload = dict(value)
        try:
            if "git" in payload:
                return GitVersion.model_validate(payload)
            if any(key in payload for key in ("major", "minor", "patch", "pre", "build")):
                return SemverDictVersion.model_validate(payload)
        except ValidationError as exc:
            raise DocumentVersionError(_format_validation_error(exc, "version")) from exc
        raise DocumentVersionError(
            "version mapping must include 'git' or semver fields "
            "(major, minor, patch, optional pre/build)."
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        try:
            return SemverListVersion(parts=list(value))
        except ValidationError as exc:
            raise DocumentVersionError(_format_validation_error(exc, "version")) from exc
    raise DocumentVersionError(
        f"version field has unsupported type {type(value).__name__}; "
        "expected string, list of integers, or mapping."
    )


def _format_validation_error(exc: ValidationError, field: str) -> str:
    primary = exc.errors()[0]
    location = ".".join(str(part) for part in primary.get("loc", ()))
    location = f"{field}.{location}" if location else field
    return f"Invalid {location}: {primary.get('msg', 'invalid value')}"
