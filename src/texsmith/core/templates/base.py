"""Core classes used to load and wrap LaTeX templates."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import importlib.util
import inspect
from pathlib import Path
import shutil
import sys
from typing import Any, cast

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.adapters.latex.pyxindy import is_available as pyxindy_available
from .manifest import TemplateError, TemplateManifest, TemplateSlot


def _detect_index_engine() -> str:
    """Return the preferred index engine based on available executables."""
    if pyxindy_available():
        return "pyxindy"
    return "texindy" if shutil.which("texindy") else "makeindex"


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
    search_paths = [str(template_root)]
    common_dir = template_root.parent / "common"
    if common_dir.exists():
        search_paths.append(str(common_dir))
    loader = FileSystemLoader(search_paths)
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
        defaults = self.info.attribute_defaults()
        defaults.update(self.info.emit_defaults())
        return defaults

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
        attribute_context = self.info.resolve_attributes(overrides)
        context = dict(attribute_context)
        for key, value in self.info.emit_defaults().items():
            context.setdefault(key, value)
        if overrides:
            for key, value in overrides.items():
                if key in context and key not in self.info.emit:
                    continue
                context[key] = value

        context.setdefault("frontmatter", "")
        context.setdefault("backmatter", "")
        context.setdefault("index_entries", False)
        context.setdefault("has_index", False)
        context.setdefault("index_terms", [])
        context.setdefault("index_registry", [])
        context.setdefault("index_engine", "auto")
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

        engine = str(context.get("index_engine") or "").strip().lower()
        if not engine or engine == "auto":
            context["index_engine"] = _detect_index_engine()
        else:
            context["index_engine"] = engine

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
                    common_dir = self.root.parent / "common"
                    try:
                        relative = source_path.relative_to(common_dir)
                    except ValueError as nested_exc:
                        raise TemplateError(
                            f"Templated asset '{asset.source}' must live inside the template root "
                            "or the shared 'common' directory."
                        ) from nested_exc
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


@dataclass(slots=True)
class ResolvedAsset:
    """Resolved template asset ready to be materialised."""

    source: Path
    destination: Path
    template: bool = False
    encoding: str | None = None
    template_name: str | None = None


def _coerce_template(value: Any) -> WrappableTemplate | None:
    """Coerce an entry point payload into a ``WrappableTemplate`` instance."""
    if isinstance(value, WrappableTemplate):
        return value

    if inspect.isclass(value) and issubclass(value, WrappableTemplate):
        template_cls = cast(type[Any], value)
        try:
            instance = template_cls()
        except TypeError as exc:  # pragma: no cover - defensive
            raise TemplateError(
                "Specialised template classes exported via entry points must be ``WrappableTemplate`` "
                "instances or be instantiable without arguments."
            ) from exc
        return cast(WrappableTemplate, instance)

    if callable(value):
        produced = value()
        return _coerce_template(produced)

    if isinstance(value, (str, Path)):
        path = Path(value)
        if path.exists():
            return WrappableTemplate(path)

    return None


def load_specialised_template(path: Path) -> WrappableTemplate | None:
    """Import a template-specific module to retrieve a specialised implementation."""
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


__all__ = [
    "BaseTemplate",
    "ResolvedAsset",
    "TemplateError",
    "WrappableTemplate",
    "_build_environment",
    "_resolve_manifest_path",
    "load_specialised_template",
]
