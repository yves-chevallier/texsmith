"""Pydantic models describing LaTeX template manifests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from pathlib import Path
from typing import Any, Callable, Literal

import tomllib
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationError,
    model_validator,
)

from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.core.exceptions import LatexRenderingError


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


AttributePrimitiveType = Literal["any", "string", "integer", "float", "boolean", "list", "mapping"]
AttributeEscapeMode = Literal["latex"]


_UNSET = object()


def _lookup_path(container: Mapping[str, Any], path: str) -> tuple[Any, bool]:
    """Return a value stored at ``path`` within ``container``."""
    segments = [segment for segment in path.split(".") if segment]
    current: Any = container
    for index, segment in enumerate(segments):
        if not isinstance(current, Mapping):
            return (None, False)
        if segment not in current:
            return (None, False)
        current = current[segment]
        if current is None and index + 1 < len(segments):
            return (None, False)
    return (current, True)


def _normalise_sources(payload: Any) -> list[str]:
    if payload is None:
        return []
    if isinstance(payload, str):
        candidate = payload.strip()
        return [candidate] if candidate else []
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        tokens: list[str] = []
        for element in payload:
            if isinstance(element, str) and element.strip():
                tokens.append(element.strip())
        return tokens
    return []


_ATTRIBUTE_NORMALISERS: dict[str, Callable[[Any, "TemplateAttributeSpec", Any], Any]] = {}


def register_attribute_normaliser(
    name: str,
) -> Callable[[Callable[[Any, "TemplateAttributeSpec", Any], Any]], Callable[[Any, "TemplateAttributeSpec", Any], Any]]:
    """Decorator used to register attribute normaliser callables."""

    def decorator(
        func: Callable[[Any, "TemplateAttributeSpec", Any], Any],
    ) -> Callable[[Any, "TemplateAttributeSpec", Any], Any]:
        _ATTRIBUTE_NORMALISERS[name] = func
        return func

    return decorator


def _resolve_attribute_normaliser(
    name: str,
) -> Callable[[Any, "TemplateAttributeSpec", Any], Any]:
    try:
        return _ATTRIBUTE_NORMALISERS[name]
    except KeyError as exc:  # pragma: no cover - defensive
        raise TemplateError(f"Unknown attribute normaliser '{name}'.") from exc


@register_attribute_normaliser("paper_option")
def _normalise_paper_option(value: Any, spec: "TemplateAttributeSpec", fallback: Any) -> Any:
    valid_bases = {
        "a0",
        "a1",
        "a2",
        "a3",
        "a4",
        "a5",
        "a6",
        "b0",
        "b1",
        "b2",
        "b3",
        "b4",
        "b5",
        "b6",
        "letter",
        "legal",
        "executive",
    }

    if value is None or value == "":
        return fallback
    if not isinstance(value, str):
        raise TemplateError(
            f"Invalid paper option type '{type(value).__name__}' for attribute '{spec.name}'."
        )

    candidate = value.strip().lower()
    if not candidate:
        return fallback

    if candidate.endswith("paper"):
        candidate = candidate[:-5]

    if candidate not in valid_bases:
        allowed = ", ".join(sorted(f"{base}paper" for base in valid_bases))
        raise TemplateError(
            f"Invalid paper option '{value}' for attribute '{spec.name}'. Allowed values: {allowed}."
        )

    return f"{candidate}paper"


@register_attribute_normaliser("orientation")
def _normalise_orientation(value: Any, spec: "TemplateAttributeSpec", fallback: Any) -> Any:
    valid_orientations = {"portrait", "landscape"}

    if value is None or value == "":
        return fallback

    if isinstance(value, str):
        candidate = value.strip().lower()
    else:
        raise TemplateError(
            f"Invalid orientation type '{type(value).__name__}' for attribute '{spec.name}'."
        )

    if not candidate:
        return fallback

    if candidate not in valid_orientations:
        allowed = ", ".join(sorted(valid_orientations))
        raise TemplateError(
            f"Invalid orientation option '{value}' for attribute '{spec.name}'. "
            f"Allowed values: {allowed}."
        )

    return candidate


@register_attribute_normaliser("babel_language")
def _normalise_language(value: Any, spec: "TemplateAttributeSpec", fallback: Any) -> Any:
    if value is None or value == "":
        return fallback

    if not isinstance(value, str):
        candidate = str(value)
    else:
        candidate = value

    mapped = _map_babel_language(candidate)
    if mapped:
        return mapped

    if fallback is not None:
        return fallback

    raise TemplateError(
        f"Attribute '{spec.name}' received unsupported language value '{value}'."
    )


class TemplateAttributeSpec(BaseModel):
    """Typed attribute definition used to build template defaults."""

    model_config = ConfigDict(extra="forbid")

    default: Any = None
    type: AttributePrimitiveType | None = None
    choices: list[Any] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    escape: AttributeEscapeMode | None = None
    normaliser: str | None = None
    required: bool = False
    allow_empty: bool = True

    # Populated lazily after validation
    name: str = ""

    # Private caches
    _default_cache: Any = PrivateAttr(default=_UNSET)

    @model_validator(mode="before")
    @classmethod
    def _coerce_sources(cls, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, Mapping):
            return data
        coerced = dict(data)
        coerced["sources"] = _normalise_sources(data.get("sources"))
        return coerced

    @model_validator(mode="after")
    def _finalise(self) -> "TemplateAttributeSpec":
        self._default_cache = self._coerce_value(
            self.default,
            from_override=False,
            is_default=True,
            fallback=None,
        )
        return self

    def default_value(self) -> Any:
        """Return a deep copy of the attribute default."""
        return copy.deepcopy(self._default_cache)

    def _effective_type(self) -> AttributePrimitiveType:
        if self.type:
            return self.type
        default = self.default
        if isinstance(default, bool):
            return "boolean"
        if isinstance(default, int) and not isinstance(default, bool):
            return "integer"
        if isinstance(default, float):
            return "float"
        if isinstance(default, str):
            return "string"
        if isinstance(default, Mapping):
            return "mapping"
        if isinstance(default, Sequence) and not isinstance(default, (str, bytes)):
            return "list"
        return "any"

    def effective_sources(self) -> list[str]:
        if self.sources:
            return list(self.sources)
        # Allow nested `press.press.*` to support legacy front matter.
        return [
            f"press.press.{self.name}",
            f"press.{self.name}",
            self.name,
        ]

    def fetch_override(
        self,
        overrides: Mapping[str, Any],
    ) -> tuple[Any, bool]:
        for path in self.effective_sources():
            if not path:
                continue
            value, found = _lookup_path(overrides, path)
            if found:
                return (value, True)
        return (_UNSET, False)

    def coerce_value(self, value: Any, *, from_override: bool) -> Any:
        fallback = self._default_cache if self._default_cache is not _UNSET else None
        result = self._coerce_value(
            value,
            from_override=from_override,
            is_default=False,
            fallback=fallback,
        )
        if result is None and self.required:
            raise TemplateError(f"Attribute '{self.name}' requires a value.")
        return result

    def _coerce_value(
        self,
        value: Any,
        *,
        from_override: bool,
        is_default: bool,
        fallback: Any,
    ) -> Any:
        target_type = self._effective_type()

        if value is None:
            result: Any = None
        elif target_type == "string":
            if isinstance(value, str):
                result = value.strip()
            else:
                result = str(value).strip()
            if not result and not self.allow_empty:
                result = None
        elif target_type == "integer":
            try:
                result = int(value)
            except (TypeError, ValueError) as exc:
                raise TemplateError(
                    f"Attribute '{self.name}' expects an integer value."
                ) from exc
        elif target_type == "float":
            try:
                result = float(value)
            except (TypeError, ValueError) as exc:
                raise TemplateError(
                    f"Attribute '{self.name}' expects a numeric value."
                ) from exc
        elif target_type == "boolean":
            if isinstance(value, bool):
                result = value
            elif isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "yes", "1", "on"}:
                    result = True
                elif lowered in {"false", "no", "0", "off"}:
                    result = False
                else:
                    raise TemplateError(
                        f"Attribute '{self.name}' expects a boolean value."
                    )
            elif isinstance(value, (int, float)):
                result = bool(value)
            else:
                raise TemplateError(
                    f"Attribute '{self.name}' expects a boolean-compatible value."
                )
        elif target_type == "list":
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                result = [copy.deepcopy(item) for item in value]
            elif isinstance(value, str):
                tokens = [item.strip() for item in value.split(",")]
                result = [token for token in tokens if token]
            else:
                result = [value]
        elif target_type == "mapping":
            if isinstance(value, Mapping):
                result = dict(value)
            else:
                raise TemplateError(f"Attribute '{self.name}' expects a mapping value.")
        else:
            result = copy.deepcopy(value)

        if self.normaliser and result is not None:
            normaliser = _resolve_attribute_normaliser(self.normaliser)
            result = normaliser(result, self, fallback)

        if self.choices and result is not None and result not in self.choices:
            allowed = ", ".join(str(choice) for choice in self.choices)
            raise TemplateError(
                f"Attribute '{self.name}' value '{result}' is invalid. Expected one of: {allowed}."
            )

        if self.escape == "latex" and isinstance(result, str) and from_override and not is_default:
            result = escape_latex_chars(result)

        return copy.deepcopy(result)


class TemplateAttributeResolver:
    """Resolve attribute values from overrides using a typed specification."""

    def __init__(self, specs: Mapping[str, TemplateAttributeSpec]):
        self._specs = dict(specs)

    def defaults(self) -> dict[str, Any]:
        return {name: spec.default_value() for name, spec in self._specs.items()}

    def merge(self, overrides: Mapping[str, Any] | None) -> dict[str, Any]:
        resolved = self.defaults()
        if not overrides:
            return resolved

        for name, spec in self._specs.items():
            value, from_override = spec.fetch_override(overrides)
            if value is _UNSET:
                continue
            coerced = spec.coerce_value(value, from_override=from_override)
            resolved[name] = coerced

        return resolved


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
    attributes: dict[str, TemplateAttributeSpec] = Field(default_factory=dict)
    assets: dict[str, TemplateAsset] = Field(default_factory=dict)
    slots: dict[str, TemplateSlot] = Field(default_factory=dict)

    _attribute_resolver: TemplateAttributeResolver = PrivateAttr()
    _attribute_defaults: dict[str, Any] = PrivateAttr(default_factory=dict)

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

    @model_validator(mode="before")
    @classmethod
    def _normalise_attributes(cls, data: dict[str, Any]) -> dict[str, Any]:
        attributes = data.get("attributes")
        if not isinstance(attributes, Mapping):
            return data

        normalised: dict[str, Any] = {}
        for name, payload in attributes.items():
            if isinstance(payload, TemplateAttributeSpec):
                normalised[name] = payload
            elif isinstance(payload, Mapping):
                if "default" not in payload and "type" not in payload:
                    normalised[name] = {"default": payload}
                else:
                    normalised[name] = payload
            else:
                normalised[name] = {"default": payload}

        updated = dict(data)
        updated["attributes"] = normalised
        return updated

    @model_validator(mode="after")
    def _bind_attribute_names(self) -> "TemplateInfo":
        for name, spec in self.attributes.items():
            spec.name = name
        self._attribute_resolver = TemplateAttributeResolver(self.attributes)
        self._attribute_defaults = self._attribute_resolver.defaults()
        return self

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

    def attribute_defaults(self) -> dict[str, Any]:
        """Return a deep copy of template attribute defaults."""
        return copy.deepcopy(self._attribute_defaults)

    def get_attribute_default(self, name: str, default: Any | None = None) -> Any:
        return copy.deepcopy(self._attribute_defaults.get(name, default))

    def resolve_attributes(self, overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Return defaults merged with overrides using the attribute specification."""
        return self._attribute_resolver.merge(overrides)


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
    "TemplateAttributeSpec",
    "TemplateError",
    "TemplateInfo",
    "TemplateManifest",
    "TemplateSlot",
]
def _map_babel_language(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    lowered = candidate.lower().replace("_", "-")
    if lowered in _BABEL_LANGUAGE_ALIASES:
        return _BABEL_LANGUAGE_ALIASES[lowered]
    primary = lowered.split("-", 1)[0]
    if primary in _BABEL_LANGUAGE_ALIASES:
        return _BABEL_LANGUAGE_ALIASES[primary]
    if lowered.isalpha():
        return lowered
    return None
