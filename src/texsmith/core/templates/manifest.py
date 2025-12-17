"""Pydantic models describing LaTeX template manifests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from pathlib import Path
import re
from typing import Any, Callable, Literal

try:  # Python >=3.11
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationError,
    model_validator,
)

from bs4 import BeautifulSoup, NavigableString, Tag

from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown
from texsmith.core.exceptions import LatexRenderingError
from texsmith.core.metadata import PressMetadataError, normalise_press_metadata
from texsmith.core.partials import normalise_partial_key


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
    description: str | None = None

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
        base = fallback
        if self.base_level is not None:
            base = self.base_level
        elif self.depth is not None:
            base = fallback + LATEX_HEADING_LEVELS[self.depth]
        return base + self.offset


AttributePrimitiveType = Literal["any", "string", "integer", "float", "boolean", "list", "mapping"]
AttributeFormatType = Literal["markdown", "raw"]
AttributeEscapeMode = Literal["latex"]


_UNSET = object()
_CODE_ENGINES = {"minted", "listings", "verbatim", "pygments"}


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


def _render_attribute_markdown(value: str, language: str = DEFAULT_TEMPLATE_LANGUAGE) -> str:
    """Render a short Markdown snippet through the standard TeXSmith pipeline."""
    from texsmith.adapters.latex.formatter import LaTeXFormatter
    from texsmith.adapters.latex.renderer import LaTeXRenderer
    from texsmith.core.config import BookConfig
    from texsmith.core.conversion.core import render_with_fallback

    document = render_markdown(value, DEFAULT_MARKDOWN_EXTENSIONS)
    html = document.html

    config = BookConfig(
        project_dir=Path("."),
        language=language or DEFAULT_TEMPLATE_LANGUAGE,
        legacy_latex_accents=False,
    )

    formatter = LaTeXFormatter()
    renderer_kwargs = {
        "output_root": Path("."),
        "copy_assets": False,
        "convert_assets": False,
        "hash_assets": False,
        "parser": "html.parser",
    }

    def _renderer_factory() -> LaTeXRenderer:
        return LaTeXRenderer(config=config, formatter=formatter, **renderer_kwargs)

    rendered, _ = render_with_fallback(
        _renderer_factory,
        html,
        runtime={"language": config.language, "copy_assets": False, "convert_assets": False, "hash_assets": False},
        bibliography={},
        state=None,
        emitter=None,
    )
    return rendered.strip()


def _render_attribute_markdown(value: str) -> str:
    """Render a short Markdown snippet into LaTeX-safe text."""
    doc = render_markdown(value, DEFAULT_MARKDOWN_EXTENSIONS)
    html = doc.html
    soup = BeautifulSoup(html, "html.parser")

    def render_node(node: Tag | NavigableString) -> str:
        if isinstance(node, NavigableString):
            return escape_latex_chars(str(node))

        name = (node.name or "").lower()
        classes = set(node.get("class") or [])
        rendered_children = "".join(render_node(child) for child in node.children)

        if name in {"strong", "b"}:
            return rf"\textbf{{{rendered_children}}}"
        if name in {"em", "i"}:
            return rf"\emph{{{rendered_children}}}"
        if name == "code":
            return rf"\texttt{{{rendered_children}}}"
        if name == "span" and "texsmith-smallcaps" in classes:
            return rf"\textsc{{{rendered_children}}}"
        if name == "br":
            return r"\\"
        if name == "p":
            return rendered_children + "\n\n"
        if name == "li":
            return "- " + rendered_children + "\n"
        return rendered_children

    body = soup.body if soup.body else soup
    rendered = "".join(render_node(child) for child in body.children)
    return rendered.strip()


_ATTRIBUTE_NORMALISERS: dict[str, Callable[[Any, "TemplateAttributeSpec", Any], Any]] = {}


def _register_attribute_normaliser(
    name: str,
) -> Callable[[Callable[[Any, "TemplateAttributeSpec", Any], Any]], Callable[[Any, "TemplateAttributeSpec", Any], Any]]:
    """Decorator used to register attribute normaliser callables (internal use)."""

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


@_register_attribute_normaliser("paper_option")
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


@_register_attribute_normaliser("orientation")
def _normalise_orientation(value: Any, spec: "TemplateAttributeSpec", fallback: Any) -> Any:
    valid_orientations = {"portrait", "landscape"}

    if value is None or value == "":
        return fallback

    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate == "vertical":
            candidate = "portrait"
        elif candidate == "horizontal":
            candidate = "landscape"
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


@_register_attribute_normaliser("babel_language")
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


@_register_attribute_normaliser("callout_style")
def _normalise_callout_style_attribute(
    value: Any, spec: "TemplateAttributeSpec", fallback: Any
) -> Any:
    allowed = {"fancy", "classic", "minimal"}
    if value is None or value == "":
        return fallback

    if isinstance(value, str):
        candidate = value.strip().lower()
    else:
        candidate = str(value).strip().lower()

    if not candidate:
        return fallback

    if candidate not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise TemplateError(
            f"Attribute '{spec.name}' value '{value}' is invalid. Expected one of: {allowed_values}."
        )

    return candidate


@_register_attribute_normaliser("margin_style")
def _normalise_margin_style(value: Any, spec: "TemplateAttributeSpec", fallback: Any) -> Any:
    if value is None or value == "":
        return fallback

    if isinstance(value, str):
        candidate = value.strip()
    else:
        candidate = str(value).strip()

    lowered = candidate.lower()
    if lowered in {"narrow", "default", "wide"}:
        return lowered
    return candidate


@_register_attribute_normaliser("code_options")
def _normalise_code_options(value: Any, spec: "TemplateAttributeSpec", fallback: Any) -> Any:
    """Normalise code highlighting options ensuring a supported engine."""

    def _pick_engine(candidate: Any) -> str:
        if isinstance(candidate, str):
            engine = candidate.strip().lower()
        else:
            engine = str(candidate).strip().lower() if candidate is not None else ""
        if not engine:
            return "pygments"
        if engine not in _CODE_ENGINES:
            allowed = ", ".join(sorted(_CODE_ENGINES))
            raise TemplateError(
                f"Attribute '{spec.name}' value '{engine}' is invalid. Expected one of: {allowed}."
            )
        return engine

    def _pick_style(candidate: Any, default: str) -> str:
        if isinstance(candidate, str):
            stripped = candidate.strip()
            return stripped or default
        if candidate is None:
            return default
        stripped = str(candidate).strip()
        return stripped or default

    fallback_engine = (
        _pick_engine(fallback.get("engine")) if isinstance(fallback, Mapping) else "pygments"
    )
    fallback_style = (
        _pick_style(fallback.get("style"), "bw") if isinstance(fallback, Mapping) else "bw"
    )
    options: dict[str, Any] = {"engine": fallback_engine, "style": fallback_style}

    if value is None:
        return options

    if isinstance(value, Mapping):
        engine_value = value.get("engine", fallback_engine)
        style_value = value.get("style", fallback_style)
        options = dict(value)
        options["engine"] = _pick_engine(engine_value)
        options["style"] = _pick_style(style_value, fallback_style)
        return options

    if isinstance(value, str):
        engine_value = value.strip()
        if not engine_value:
            return options
        options["engine"] = _pick_engine(engine_value)
        return options

    options["engine"] = fallback_engine
    return options


class TemplateAttributeSpec(BaseModel):
    """Typed attribute definition used to build template defaults."""

    model_config = ConfigDict(extra="forbid")

    default: Any = None
    type: AttributePrimitiveType | None = None
    format: AttributeFormatType = "markdown"
    choices: list[Any] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    escape: AttributeEscapeMode | None = None
    normaliser: str | None = None
    required: bool = False
    allow_empty: bool = True
    description: str | None = None
    range: list[Any] | None = None
    owner: str | None = None

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
        return [self.name]

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
            if result and self.format == "markdown":
                result = _render_attribute_markdown(result)
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

        if (
            self.escape == "latex"
            and isinstance(result, str)
            and from_override
            and not is_default
            and self.format != "markdown"
        ):
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

        override_payload = dict(overrides)
        try:
            normalise_press_metadata(override_payload)
        except PressMetadataError:
            pass

        for name, spec in self._specs.items():
            value, from_override = spec.fetch_override(override_payload)
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
    fragments: list[str] | None = None
    override: list[str] = Field(default_factory=list)
    required_partials: list[str] = Field(default_factory=list)
    attributes: dict[str, TemplateAttributeSpec] = Field(default_factory=dict)
    assets: dict[str, TemplateAsset] = Field(default_factory=dict)
    slots: dict[str, TemplateSlot] = Field(default_factory=dict)
    emit: dict[str, Any] = Field(default_factory=dict)

    _attribute_resolver: TemplateAttributeResolver = PrivateAttr()
    _attribute_defaults: dict[str, Any] = PrivateAttr(default_factory=dict)
    _attribute_owners: dict[str, str] = PrivateAttr(default_factory=dict)

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
            if spec.owner is None:
                spec.owner = self.name
            self._attribute_owners[name] = spec.owner
        self._attribute_resolver = TemplateAttributeResolver(self.attributes)
        self._attribute_defaults = self._attribute_resolver.defaults()
        normalised_required: list[str] = []
        for entry in self.required_partials or []:
            if not isinstance(entry, str):
                continue
            key = normalise_partial_key(entry)
            if key:
                normalised_required.append(key)
        self.required_partials = normalised_required
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

    def emit_defaults(self) -> dict[str, Any]:
        """Return default attributes emitted by the template."""
        return copy.deepcopy(self.emit)

    def get_attribute_default(self, name: str, default: Any | None = None) -> Any:
        return copy.deepcopy(self._attribute_defaults.get(name, default))

    def resolve_attributes(self, overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Return defaults merged with overrides using the attribute specification."""
        return self._attribute_resolver.merge(overrides)

    def attribute_owners(self) -> dict[str, str]:
        """Return attribute ownership map (name -> owner)."""
        return dict(self._attribute_owners)


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
