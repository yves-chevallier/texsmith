"""Pydantic models describing LaTeX template manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomllib
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from texsmith.domain.exceptions import LatexRenderingError


class TemplateError(LatexRenderingError):
    """Raised when a LaTeX template cannot be loaded or rendered."""


DEFAULT_TEMPLATE_LANGUAGE = "english"

_BABEL_LANGUAGE_ALIASES = {
    "ad": "catalan",
    "ca": "catalan",
    "cs": "czech",
    "da": "danish",
    "de": "ngerman",
    "de-de": "ngerman",
    "en": "english",
    "en-gb": "british",
    "en-us": "english",
    "en-au": "australian",
    "en-ca": "canadian",
    "es": "spanish",
    "es-es": "spanish",
    "es-mx": "mexican",
    "fi": "finnish",
    "fr": "french",
    "fr-fr": "french",
    "fr-ca": "canadien",
    "it": "italian",
    "nl": "dutch",
    "nb": "norwegian",
    "nn": "nynorsk",
    "pl": "polish",
    "pt": "portuguese",
    "pt-br": "brazilian",
    "ro": "romanian",
    "ru": "russian",
    "sk": "slovak",
    "sl": "slovene",
    "sv": "swedish",
    "tr": "turkish",
}

LATEX_HEADING_LEVELS: dict[str, int] = {
    "part": -1,
    "chapter": 0,
    "section": 1,
    "subsection": 2,
    "subsubsection": 3,
    "paragraph": 4,
    "subparagraph": 5,
}


class CompatInfo(BaseModel):
    """Compatibility constraints declared by the template."""

    model_config = ConfigDict(extra="ignore")

    texsmith: str | None = None


class TemplateAsset(BaseModel):
    """Description of individual template assets."""

    model_config = ConfigDict(extra="forbid")

    source: str
    template: bool = False
    encoding: str | None = None


class TemplateSlot(BaseModel):
    """Configuration describing how content is injected into a template slot."""

    model_config = ConfigDict(extra="forbid")

    base_level: int | None = None
    depth: str | None = None
    offset: int = 0
    default: bool = False
    strip_heading: bool = False

    @model_validator(mode="after")
    def _validate_depth(self) -> TemplateSlot:
        if self.depth is not None and self.depth not in LATEX_HEADING_LEVELS:
            raise ValueError(
                f"Unsupported slot depth '{self.depth}', "
                f"expected one of {', '.join(LATEX_HEADING_LEVELS)}."
            )
        return self

    def resolve_level(self, fallback: int) -> int:
        """Return the base level applied to rendered headings for this slot."""
        level = fallback
        if self.base_level is not None:
            level = self.base_level
        elif self.depth is not None:
            level = LATEX_HEADING_LEVELS[self.depth]
        return level + self.offset


class TemplateInfo(BaseModel):
    """Metadata describing the LaTeX template payload."""

    model_config = ConfigDict(extra="allow")

    name: str
    version: str
    entrypoint: str = "template.tex"
    engine: str | None = None
    shell_escape: bool = False
    texlive_year: int | None = None
    tlmgr_packages: list[str] = Field(default_factory=list)
    override: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    assets: dict[str, TemplateAsset] = Field(default_factory=dict)
    slots: dict[str, TemplateSlot] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalise_assets(cls, data: dict[str, Any]) -> dict[str, Any]:
        assets = data.get("assets")
        if isinstance(assets, dict):
            normalised: dict[str, Any] = {}
            for destination, spec in assets.items():
                if isinstance(spec, str):
                    normalised[destination] = {"source": spec}
                else:
                    normalised[destination] = spec
            data = dict(data)
            data["assets"] = normalised
        return data

    def resolve_slots(self) -> tuple[dict[str, TemplateSlot], str]:
        """Return declared slots ensuring a single default sink exists."""
        resolved = {
            name: slot if isinstance(slot, TemplateSlot) else TemplateSlot.model_validate(slot)
            for name, slot in self.slots.items()
        }

        if "mainmatter" not in resolved:
            resolved["mainmatter"] = TemplateSlot(default=True)

        defaults = [name for name, slot in resolved.items() if slot.default]
        if not defaults:
            resolved["mainmatter"] = resolved["mainmatter"].model_copy(update={"default": True})
            defaults = ["mainmatter"]
        elif len(defaults) > 1:
            formatted = ", ".join(defaults)
            raise TemplateError(f"Multiple default slots declared: {formatted}")

        return resolved, defaults[0]


class LatexSection(BaseModel):
    """Section grouping LaTeX-specific manifest settings."""

    template: TemplateInfo


class TemplateManifest(BaseModel):
    """Structured manifest describing a LaTeX template."""

    compat: CompatInfo | None = None
    latex: LatexSection

    @classmethod
    def load(cls, manifest_path: Path) -> TemplateManifest:
        """Load and validate a manifest from disk."""
        try:
            content = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:  # pragma: no cover - sanity check
            raise TemplateError(f"Template manifest is missing: {manifest_path}") from exc
        except OSError as exc:  # pragma: no cover - IO failure
            raise TemplateError(f"Failed to read template manifest: {exc}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise TemplateError(f"Invalid template manifest: {exc}") from exc

        try:
            return cls.model_validate(content)
        except ValidationError as exc:
            raise TemplateError(f"Template manifest validation failed: {exc}") from exc


__all__ = [
    "CompatInfo",
    "DEFAULT_TEMPLATE_LANGUAGE",
    "LATEX_HEADING_LEVELS",
    "LatexSection",
    "TemplateAsset",
    "TemplateError",
    "TemplateInfo",
    "TemplateManifest",
    "TemplateSlot",
]
