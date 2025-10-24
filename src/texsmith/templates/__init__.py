"""Template loading and rendering helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from importlib import metadata
import importlib.util
import inspect
from pathlib import Path
import shutil
import sys
import tomllib
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..exceptions import LatexRenderingError
from ..utils import escape_latex_chars


if TYPE_CHECKING:
    from ..formatter import LaTeXFormatter


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


LATEX_HEADING_LEVELS: dict[str, int] = {
    "part": -1,
    "chapter": 0,
    "section": 1,
    "subsection": 2,
    "subsubsection": 3,
    "paragraph": 4,
    "subparagraph": 5,
}


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


def _resolve_manifest_path(root: Path) -> Path:
    candidates = (root / "manifest.toml", root / "template" / "manifest.toml")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise TemplateError(
        f"Unable to locate template manifest under '{root}'. "
        "Expected 'manifest.toml' at the root or inside a 'template' directory."
    )


def _build_environment(template_root: Path) -> Environment:
    loader = FileSystemLoader(str(template_root))
    environment = Environment(
        loader=loader,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
    )
    environment.filters.setdefault("latex_escape", escape_latex_chars)
    environment.filters.setdefault("escape_latex", escape_latex_chars)
    return environment


class BaseTemplate:
    """Base class shared by template implementations."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        if not self.root.exists():
            raise TemplateError(f"Template root does not exist: {self.root}")

        manifest_path = _resolve_manifest_path(self.root)
        self.manifest = TemplateManifest.load(manifest_path)
        self.info = self.manifest.latex.template
        self.environment = _build_environment(self.root)

    def default_context(self) -> dict[str, Any]:
        """Return a shallow copy of the manifest default attributes."""
        return dict(self.info.attributes)

    def render_template(self, template_name: str, **context: Any) -> str:
        """Render a template using the configured Jinja environment."""
        try:
            template = self.environment.get_template(template_name)
        except TemplateNotFound as exc:
            raise TemplateError(
                f"Template entry '{template_name}' is missing in {self.root}"
            ) from exc
        return template.render(context)


class WrappableTemplate(BaseTemplate):
    """Template capable of wrapping a generated LaTeX fragment."""

    def prepare_context(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the rendering context shared by the template and its assets."""
        context = self.default_context()
        if overrides:
            context.update(overrides)

        context.setdefault("frontmatter", "")
        context.setdefault("backmatter", "")
        context.setdefault("index_entries", False)
        context.setdefault("acronyms", {})
        context.setdefault("citations", [])
        context.setdefault("bibliography_entries", {})
        context.setdefault("bibliography_resource", None)

        slots, default_slot = self.info.resolve_slots()
        for name in slots:
            context.setdefault(name, "")

        if default_slot == "mainmatter":
            context["mainmatter"] = latex_body
        else:
            context.setdefault("mainmatter", "")
            context[default_slot] = latex_body

        return context

    def wrap_document(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        """Render the template entry point using the provided LaTeX payload."""
        if context is None:
            context = self.prepare_context(latex_body, overrides=overrides)
        else:
            context = dict(context)
            context.setdefault("frontmatter", "")
            context.setdefault("backmatter", "")
            slots, default_slot = self.info.resolve_slots()
            for name in slots:
                context.setdefault(name, "")
            if default_slot == "mainmatter":
                context["mainmatter"] = latex_body
            else:
                context.setdefault("mainmatter", "")
                context[default_slot] = latex_body

        return self.render_template(self.info.entrypoint, **context)

    def iter_assets(self) -> Iterable[ResolvedAsset]:
        """Yield declared template assets."""
        for destination, asset in self.info.assets.items():
            dest_path = Path(destination)
            if dest_path.is_absolute():
                raise TemplateError(
                    f"Template asset destination must be relative, got '{destination}'."
                )

            source_path = Path(asset.source)
            if not source_path.is_absolute():
                source_path = (self.root / source_path).resolve()
            if not source_path.exists():
                raise TemplateError(
                    f"Declared template asset '{asset.source}' is missing under {self.root}."
                )

            template_name: str | None = None
            if asset.template:
                if source_path.is_dir():
                    raise TemplateError(
                        f"Templated assets must reference files, got directory '{asset.source}'."
                    )
                try:
                    relative = source_path.relative_to(self.root)
                except ValueError as exc:  # pragma: no cover - defensive
                    raise TemplateError(
                        f"Templated asset '{asset.source}' must live inside the template root."
                    ) from exc
                template_name = relative.as_posix()

            yield ResolvedAsset(
                source=source_path,
                destination=dest_path,
                template=asset.template,
                encoding=asset.encoding,
                template_name=template_name,
            )

    def iter_formatter_overrides(self) -> Iterable[tuple[str, Path]]:
        """Yield formatter override templates declared by the manifest."""
        if not self.info.override:
            return ()

        search_roots = [
            self.root / "overrides",
            self.root / "template" / "overrides",
            self.root,
            self.root.parent / "overrides",
        ]

        seen: set[str] = set()
        overrides: list[tuple[str, Path]] = []

        for entry in self.info.override:
            if not isinstance(entry, str):
                raise TemplateError("Formatter override entries must be provided as string paths.")
            candidate = entry.strip()
            if not candidate:
                continue

            relative_path = Path(candidate)
            if relative_path.is_absolute() or any(part == ".." for part in relative_path.parts):
                raise TemplateError(
                    f"Formatter override '{entry}' must be a relative path without '..'."
                )

            resolved_path: Path | None = None
            for root in search_roots:
                if not root.exists():
                    continue
                probe = (root / relative_path).resolve()
                if probe.exists():
                    resolved_path = probe
                    break

            if resolved_path is None:
                raise TemplateError(f"Formatter override '{entry}' is missing under '{self.root}'.")

            key = relative_path.with_suffix("").as_posix().replace("/", "_")
            if key in seen:
                continue
            seen.add(key)
            overrides.append((key, resolved_path))

        return overrides


def _load_path_template(path: Path) -> WrappableTemplate:
    specialised = _load_specialised_template(path)
    if specialised is not None:
        return specialised
    return WrappableTemplate(path)


def _load_specialised_template(path: Path) -> WrappableTemplate | None:
    init_path = path / "__init__.py"
    if not init_path.exists():
        return None

    resolved_init = init_path.resolve()
    module_name = f"_texsmith_template_{hash(resolved_init) & 0xFFFFFFFF:x}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        resolved_init,
        submodule_search_locations=[str(path.resolve())],
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - surface import errors
        sys.modules.pop(module_name, None)
        raise TemplateError(f"Failed to import template module at '{path}': {exc}") from exc

    for attribute in ("Template", "template", "load_template", "get_template"):
        candidate = getattr(module, attribute, None)
        if candidate is None:
            continue
        specialised = _coerce_template(candidate)
        if specialised is not None:
            return specialised

    return None


@dataclass(slots=True)
class ResolvedAsset:
    """Resolved template asset ready to be materialised."""

    source: Path
    destination: Path
    template: bool = False
    encoding: str | None = None
    template_name: str | None = None


def load_template(identifier: str) -> WrappableTemplate:
    """Load a template selected by name or filesystem path."""
    path_candidate = Path(identifier).expanduser()
    if path_candidate.exists():
        return _load_path_template(path_candidate)

    if not path_candidate.is_absolute():
        slug = _slug_from_identifier(identifier)
        for candidate in _iter_local_candidates(path_candidate, slug):
            if candidate.exists():
                return _load_path_template(candidate)

    entry_points = metadata.entry_points()
    group = entry_points.select(group="texsmith.templates")

    for entry_point in _match_entry_points(group, identifier):
        loaded = entry_point.load()
        template = _coerce_template(loaded)
        if template is not None:
            return template

    raise TemplateError(
        f"Unable to load template '{identifier}'. Provide a valid path or "
        "install a package exposing a 'texsmith.templates' entry point."
    )


def _match_entry_points(
    entry_points: Iterable[metadata.EntryPoint],
    name: str,
) -> Iterable[metadata.EntryPoint]:
    for entry_point in entry_points:
        if entry_point.name == name:
            yield entry_point


def _coerce_template(value: Any) -> WrappableTemplate | None:
    """Coerce an entry point payload into a ``WrappableTemplate`` instance."""
    if isinstance(value, WrappableTemplate):
        return value

    if inspect.isclass(value) and issubclass(value, WrappableTemplate):
        return value()

    if callable(value):
        produced = value()
        return _coerce_template(produced)

    if isinstance(value, (str, Path)):
        path = Path(value)
        if path.exists():
            return WrappableTemplate(path)

    return None


def copy_template_assets(
    template: WrappableTemplate,
    output_dir: Path,
    *,
    context: Mapping[str, Any] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> list[Path]:
    """Copy the template declared assets into the selected output directory."""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if context is None:
        render_context = template.prepare_context("", overrides=overrides)
    else:
        render_context = dict(context)

    written: list[Path] = []
    for asset in template.iter_assets():
        destination_path = (output_dir / asset.destination).resolve()

        if asset.template:
            if asset.template_name is None:  # pragma: no cover - defensive
                raise TemplateError(
                    f"Templated asset '{asset.source}' is missing template metadata."
                )
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            rendered = template.render_template(asset.template_name, **render_context)
            destination_path.write_text(
                rendered,
                encoding=asset.encoding or "utf-8",
            )
        elif asset.source.is_dir():
            shutil.copytree(asset.source, destination_path, dirs_exist_ok=True)
        else:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset.source, destination_path)

        written.append(destination_path)

    return written


def _slug_from_identifier(identifier: str) -> str:
    path = Path(identifier)
    slug = path.name
    if slug in {".", ""}:
        slug = identifier.strip("./")
    return slug


def _iter_local_candidates(initial: Path, slug: str) -> Iterable[Path]:
    """Yield additional candidate locations for local templates."""
    candidates: list[Path] = []
    if str(initial) not in {slug, f"./{slug}", f".\\{slug}"}:
        candidates.append(initial)

    cwd = Path.cwd()
    templates_root = cwd / "templates"
    distribution_name = f"texsmith-template-{slug}"
    package_name = f"texsmith_template_{slug}"

    candidates.extend(
        [
            cwd / slug,
            cwd / package_name,
            cwd / distribution_name / package_name,
            templates_root / slug,
            cwd / distribution_name,
            templates_root / distribution_name / package_name,
            templates_root / package_name,
            templates_root / distribution_name,
        ]
    )

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        yield candidate


@dataclass(slots=True)
class TemplateRuntime:
    """Resolved template metadata reused across conversions."""

    instance: WrappableTemplate
    name: str
    engine: str | None
    requires_shell_escape: bool
    slots: dict[str, TemplateSlot]
    default_slot: str
    formatter_overrides: dict[str, Path]
    base_level: int | None


@dataclass(slots=True)
class TemplateBinding:
    """Binding between slot requests and a LaTeX template."""

    runtime: TemplateRuntime | None
    instance: WrappableTemplate | None
    name: str | None
    engine: str | None
    requires_shell_escape: bool
    formatter_overrides: dict[str, Path]
    slots: dict[str, TemplateSlot]
    default_slot: str
    base_level: int | None

    def slot_levels(self, *, offset: int = 0) -> dict[str, int]:
        """Return the resolved base level for each slot."""
        base = (self.base_level or 0) + offset
        return {name: slot.resolve_level(base) for name, slot in self.slots.items()}

    def apply_formatter_overrides(self, formatter: LaTeXFormatter) -> None:
        """Apply template-provided overrides to a formatter."""
        for key, override_path in self.formatter_overrides.items():
            formatter.override_template(key, override_path)


def coerce_base_level(value: Any, *, allow_none: bool = True) -> int | None:
    if value is None:
        if allow_none:
            return None
        raise TemplateError("Base level value is missing.")

    if isinstance(value, bool):
        raise TemplateError("Base level must be an integer, booleans are not supported.")

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            if allow_none:
                return None
            raise TemplateError("Base level value cannot be empty.")
        try:
            return int(candidate)
        except ValueError as exc:  # pragma: no cover - defensive
            raise TemplateError(
                f"Invalid base level '{value}'. Expected an integer value."
            ) from exc

    raise TemplateError(
        f"Base level should be provided as an integer value, got type '{type(value).__name__}'."
    )


def extract_base_level_override(overrides: Mapping[str, Any] | None) -> Any:
    if not overrides:
        return None

    direct_candidate = overrides.get("base_level")
    meta_section = overrides.get("meta")
    meta_candidate = None
    if isinstance(meta_section, Mapping):
        meta_candidate = meta_section.get("base_level")

    return meta_candidate if meta_candidate is not None else direct_candidate


def build_template_overrides(front_matter: Mapping[str, Any] | None) -> dict[str, Any]:
    if not front_matter or not isinstance(front_matter, Mapping):
        return {}

    meta_section = front_matter.get("meta")
    if isinstance(meta_section, Mapping):
        return {"meta": dict(meta_section)}

    return {"meta": dict(front_matter)}


def extract_language_from_front_matter(
    front_matter: Mapping[str, Any] | None,
) -> str | None:
    if not isinstance(front_matter, Mapping):
        return None

    meta_entry = front_matter.get("meta")
    containers: tuple[Mapping[str, Any] | None, ...] = (
        meta_entry if isinstance(meta_entry, Mapping) else None,
        front_matter,
    )

    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for key in ("language", "lang"):
            value = container.get(key)
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    return stripped
    return None


def normalise_template_language(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    if not stripped:
        return None

    lowered = stripped.lower().replace("_", "-")
    alias = _BABEL_LANGUAGE_ALIASES.get(lowered)
    if alias:
        return alias

    primary = lowered.split("-", 1)[0]
    alias = _BABEL_LANGUAGE_ALIASES.get(primary)
    if alias:
        return alias

    if lowered.isalpha():
        return lowered

    return None


def resolve_template_language(
    explicit: str | None,
    front_matter: Mapping[str, Any] | None,
) -> str:
    candidates = (
        normalise_template_language(explicit),
        normalise_template_language(extract_language_from_front_matter(front_matter)),
    )

    for candidate in candidates:
        if candidate:
            return candidate

    return DEFAULT_TEMPLATE_LANGUAGE


def load_template_runtime(template: str) -> TemplateRuntime:
    """Resolve template metadata for repeated conversions."""
    template_instance = load_template(template)

    template_base = coerce_base_level(
        template_instance.info.attributes.get("base_level"),
    )

    slots, default_slot = template_instance.info.resolve_slots()
    formatter_overrides = dict(template_instance.iter_formatter_overrides())

    return TemplateRuntime(
        instance=template_instance,
        name=template_instance.info.name,
        engine=template_instance.info.engine,
        requires_shell_escape=bool(template_instance.info.shell_escape),
        slots=slots,
        default_slot=default_slot,
        formatter_overrides=formatter_overrides,
        base_level=template_base,
    )


def resolve_template_binding(
    *,
    template: str | None,
    template_runtime: TemplateRuntime | None,
    template_overrides: Mapping[str, Any],
    slot_requests: Mapping[str, str],
    warn: Callable[[str], None] | None = None,
) -> tuple[TemplateBinding, dict[str, str]]:
    runtime = template_runtime
    if runtime is None and template:
        runtime = load_template_runtime(template)

    if runtime is not None:
        binding = TemplateBinding(
            runtime=runtime,
            instance=runtime.instance,
            name=runtime.name,
            engine=runtime.engine,
            requires_shell_escape=runtime.requires_shell_escape,
            formatter_overrides=dict(runtime.formatter_overrides),
            slots=runtime.slots,
            default_slot=runtime.default_slot,
            base_level=runtime.base_level,
        )
    else:
        binding = TemplateBinding(
            runtime=None,
            instance=None,
            name=None,
            engine=None,
            requires_shell_escape=False,
            formatter_overrides={},
            slots={"mainmatter": TemplateSlot(default=True)},
            default_slot="mainmatter",
            base_level=None,
        )

    base_override = coerce_base_level(extract_base_level_override(template_overrides))
    if base_override is not None:
        binding.base_level = base_override

    filtered: dict[str, str] = {}
    for slot_name, selector in slot_requests.items():
        if slot_name not in binding.slots:
            if warn is not None:
                template_hint = f"template '{binding.name}'" if binding.name else "the template"
                warn(
                    f"slot '{slot_name}' is not defined by {template_hint}; "
                    f"content will remain in '{binding.default_slot}'."
                )
            continue
        if binding.runtime is None:
            if warn is not None:
                warn(f"slot '{slot_name}' was requested but no template is selected; ignoring.")
            continue
        filtered[slot_name] = selector

    return binding, filtered
