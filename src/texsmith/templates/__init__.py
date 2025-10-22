"""Template loading and rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import importlib.util
import inspect
from pathlib import Path
import shutil
import sys
import tomllib
from typing import Any, Iterable, Mapping

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..exceptions import LatexRenderingError
from ..utils import escape_latex_chars


class TemplateError(LatexRenderingError):
    """Raised when a LaTeX template cannot be loaded or rendered."""


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


class LatexSection(BaseModel):
    """Section grouping LaTeX-specific manifest settings."""

    template: TemplateInfo


class TemplateManifest(BaseModel):
    """Structured manifest describing a LaTeX template."""

    compat: CompatInfo | None = None
    latex: LatexSection

    @classmethod
    def load(cls, manifest_path: Path) -> "TemplateManifest":
        """Load and validate a manifest from disk."""

        try:
            content = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:  # pragma: no cover - sanity check
            raise TemplateError(
                f"Template manifest is missing: {manifest_path}"
            ) from exc
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
        context["mainmatter"] = latex_body
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
            context["mainmatter"] = latex_body

        return self.render_template(self.info.entrypoint, **context)

    def iter_assets(self) -> Iterable["ResolvedAsset"]:
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
                    "Declared template asset "
                    f"'{asset.source}' is missing under {self.root}."
                )

            template_name: str | None = None
            if asset.template:
                if source_path.is_dir():
                    raise TemplateError(
                        "Templated assets must reference files, "
                        f"got directory '{asset.source}'."
                    )
                try:
                    relative = source_path.relative_to(self.root)
                except ValueError as exc:  # pragma: no cover - defensive
                    raise TemplateError(
                        "Templated asset "
                        f"'{asset.source}' must live inside the template root."
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
                raise TemplateError(
                    "Formatter override entries must be provided as string paths."
                )
            candidate = entry.strip()
            if not candidate:
                continue

            relative_path = Path(candidate)
            if relative_path.is_absolute() or any(
                part == ".." for part in relative_path.parts
            ):
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
                raise TemplateError(
                    f"Formatter override '{entry}' is missing under '{self.root}'."
                )

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
        raise TemplateError(
            f"Failed to import template module at '{path}': {exc}"
        ) from exc

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
