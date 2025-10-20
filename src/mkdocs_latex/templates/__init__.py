"""Template loading and rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import inspect
from pathlib import Path
import shutil
from typing import Any, Iterable, Mapping

import tomllib
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..exceptions import LatexRenderingError


class TemplateError(LatexRenderingError):
    """Raised when a LaTeX template cannot be loaded or rendered."""


class CompatInfo(BaseModel):
    """Compatibility constraints declared by the template."""

    model_config = ConfigDict(extra="ignore")

    mkdocs_latex: str | None = None


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
    return Environment(
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
        return WrappableTemplate(path_candidate)

    if not path_candidate.is_absolute():
        slug = _slug_from_identifier(identifier)
        for candidate in _iter_local_candidates(path_candidate, slug):
            if candidate.exists():
                return WrappableTemplate(candidate)

    entry_points = metadata.entry_points()
    group = entry_points.select(group="mkdocs_latex.templates")

    for entry_point in _match_entry_points(group, identifier):
        loaded = entry_point.load()
        template = _coerce_template(loaded)
        if template is not None:
            return template

    raise TemplateError(
        f"Unable to load template '{identifier}'. Provide a valid path or "
        "install a package exposing a 'mkdocs_latex.templates' entry point."
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

    slug_root = Path.cwd() / f"latex_template_{slug}"
    search_roots = [
        Path.cwd(),
        Path.cwd() / "templates",
        slug_root,
        Path.cwd() / "latex_template_book",
    ]
    suffixes = [
        Path(slug),
        Path(f"mkdocs_latex_template_{slug}"),
    ]

    for root in search_roots:
        for suffix in suffixes:
            candidates.append(root / suffix)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        yield candidate
