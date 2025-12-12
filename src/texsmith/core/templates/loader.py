"""Helpers for loading template instances from disk or entry points."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from importlib import metadata
import importlib.util
from pathlib import Path
import shutil
from typing import Any

from texsmith.core.user_dir import get_user_dir

from .base import WrappableTemplate, load_specialised_template
from .builtins import iter_builtin_templates, load_builtin_template
from .manifest import TemplateError


def _looks_like_template_root(path: Path) -> bool:
    """Return True when ``path`` contains manifest or specialised template markers."""
    def _safe_exists(candidate: Path) -> bool:
        try:
            return candidate.exists()
        except OSError:
            return False

    if not _safe_exists(path) or path.is_file():
        return False
    if _safe_exists(path / "__init__.py"):
        return True
    manifest_candidates = (path / "manifest.toml", path / "template" / "manifest.toml")
    return any(_safe_exists(candidate) for candidate in manifest_candidates)


def load_template(identifier: str) -> WrappableTemplate:
    """Load a template selected by name or filesystem path."""
    path_candidate = Path(identifier).expanduser()
    looks_like_path = (
        path_candidate.is_absolute()
        or "/" in identifier
        or "\\" in identifier
        or identifier.startswith(".")
    )
    if looks_like_path and path_candidate.exists():
        return _load_path_template(path_candidate)

    slug = _slug_from_identifier(identifier)

    builtin = load_builtin_template(identifier)
    if builtin is not None:
        return builtin

    packaged_root = _resolve_packaged_template_root(slug)
    if packaged_root is not None:
        return _load_path_template(packaged_root)

    for candidate in _iter_local_candidates(slug):
        if _looks_like_template_root(candidate):
            return _load_path_template(candidate)

    home_candidate = _home_template_candidate(slug)
    if home_candidate is not None and _looks_like_template_root(home_candidate):
        return _load_path_template(home_candidate)

    raise TemplateError(
        f"Unable to load template '{identifier}'. Provide a valid path or "
        "install a package exposing a 'texsmith.templates' entry point."
    )


def copy_template_assets(
    template: WrappableTemplate,
    output_dir: Path,
    *,
    context: Mapping[str, Any] | None = None,
    overrides: Mapping[str, Any] | None = None,
    assets: Iterable["ResolvedAsset"] | None = None,
) -> list[Path]:
    """Copy the template declared assets into the selected output directory."""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if context is None:
        render_context = template.prepare_context("", overrides=overrides)
    else:
        render_context = dict(context)

    written: list[Path] = []
    asset_entries = list(assets) if assets is not None else list(template.iter_assets())
    for asset in asset_entries:
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


def _load_path_template(path: Path) -> WrappableTemplate:
    specialised = load_specialised_template(path)
    if specialised is not None:
        return specialised
    return WrappableTemplate(path)


def _match_entry_points(
    entry_points: Iterable[metadata.EntryPoint],
    name: str,
) -> Iterable[metadata.EntryPoint]:
    for entry_point in entry_points:
        if entry_point.name == name:
            yield entry_point


def _coerce_template(value: Any) -> WrappableTemplate | None:
    """Coerce an entry point payload into a ``WrappableTemplate`` instance."""
    from .base import _coerce_template as base_coerce_template

    return base_coerce_template(value)


def _slug_from_identifier(identifier: str) -> str:
    path = Path(identifier)
    slug = path.name
    if slug in {".", ""}:
        slug = identifier.strip("./")
    return slug


def _iter_local_candidates(slug: str | None) -> Iterable[Path]:
    """Yield template candidates from the current directory and its parents."""
    cwd = Path.cwd().resolve()
    visited_roots: set[Path] = set()
    current = cwd
    while current not in visited_roots:
        visited_roots.add(current)
        templates_root = current / "templates"
        roots = (current, templates_root)
        if not slug:
            for root in roots:
                if not root.exists():
                    continue
                for child in root.iterdir():
                    if child.is_dir():
                        yield child
        else:
            distribution_name = f"texsmith-template-{slug}"
            package_name = f"texsmith_template_{slug}"
            for root in roots:
                for candidate in (
                    root / slug,
                    root / package_name,
                    root / distribution_name / package_name,
                    root / distribution_name,
                ):
                    yield candidate
        if current.parent == current:
            break
        current = current.parent


def _resolve_packaged_template_root(slug: str) -> Path | None:
    """Return a template root provided by an installed Python package."""
    entry_points = metadata.entry_points()
    group = entry_points.select(group="texsmith.templates")
    for entry_point in _match_entry_points(group, slug):
        loaded = entry_point.load()
        template = _coerce_template(loaded)
        if template is not None:
            return template.root

    candidate_modules = [
        f"texsmith_template_{slug}",
        f"texsmith-template-{slug}",
        slug,
    ]
    for module_name in candidate_modules:
        spec = importlib.util.find_spec(module_name)
        if spec is None or spec.origin is None:
            continue
        origin_path = Path(spec.origin).resolve()
        module_root = origin_path.parent if origin_path.name == "__init__.py" else origin_path
        if _looks_like_template_root(module_root):
            return module_root
    return None


def _home_template_candidate(slug: str) -> Path | None:
    """Return a template path under ~/.texsmith/templates if present."""
    home_root = get_user_dir().data_dir("templates", create=False)
    distribution_name = f"texsmith-template-{slug}"
    package_name = f"texsmith_template_{slug}"
    for candidate in (
        home_root / slug,
        home_root / package_name,
        home_root / distribution_name / package_name,
        home_root / distribution_name,
    ):
        if candidate.exists():
            return candidate
    return None


def discover_templates() -> list[dict[str, str]]:
    """Return available templates in discovery order."""
    entries: list[dict[str, str]] = []

    def _record(origin: str, name: str, root: Path) -> None:
        entries.append({"name": name, "origin": origin, "root": str(root.resolve())})

    for slug in iter_builtin_templates():
        try:
            template = load_builtin_template(slug)
        except TemplateError:
            continue
        if template is not None:
            _record("builtin", slug, template.root)

    try:
        for dist in metadata.distributions():
            name = dist.metadata.get("Name", "")
            if not name.lower().startswith("texsmith-template-"):
                continue
            slug = name[len("texsmith-template-") :]
            root = _resolve_packaged_template_root(slug)
            if root is None:
                continue
            _record("package", slug, root)
    except Exception:
        pass

    seen_locals: set[str] = set()
    for candidate in _iter_local_candidates(""):
        if not _looks_like_template_root(candidate):
            continue
        key = str(candidate.resolve())
        if key in seen_locals:
            continue
        seen_locals.add(key)
        _record("local", candidate.name, candidate)

    home_root = get_user_dir().data_dir("templates", create=False)
    if home_root.exists():
        for child in sorted(home_root.iterdir()):
            if child.is_dir() and _looks_like_template_root(child):
                _record("home", child.name, child)

    return sorted(entries, key=lambda entry: (entry["origin"], entry["name"]))

    for candidate in _iter_local_candidates("*placeholder*"):
        pass

    local_candidates: list[Path] = []
    for slug in set():
        pass

    for candidate in _iter_local_candidates("*placeholder*"):
        pass

    def _record(origin: str, name: str, root: Path) -> None:
        key = (name, str(root))
        if key in seen_paths:
            return
        seen_paths.add(key)
        entries.append({"name": name, "origin": origin, "root": str(root)})

    # Re-run local with concrete names.
    visited: set[str] = set()
    cwd = Path.cwd().resolve()
    for candidate in _iter_local_candidates(""):
        if _looks_like_template_root(candidate):
            _record("local", candidate.name, candidate)

    home_root = get_user_dir().data_dir("templates", create=False)
    if home_root.exists():
        for child in home_root.iterdir():
            if child.is_dir() and _looks_like_template_root(child):
                _record("home", child.name, child)

    return sorted(entries, key=lambda entry: (entry["origin"], entry["name"]))


__all__ = [
    "copy_template_assets",
    "discover_templates",
    "load_template",
]
