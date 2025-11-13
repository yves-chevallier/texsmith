"""Helpers for loading template instances from disk or entry points."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from importlib import metadata
from pathlib import Path
import shutil
from typing import Any

from .base import WrappableTemplate, load_specialised_template
from .manifest import TemplateError


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


def _iter_local_candidates(initial: Path, slug: str) -> Iterable[Path]:
    """Yield additional candidate locations for local templates."""
    candidates: list[Path] = []
    if str(initial) not in {slug, f"./{slug}", f".\\{slug}"}:
        candidates.append(initial)

    distribution_name = f"texsmith-template-{slug}"
    package_name = f"texsmith_template_{slug}"

    def _extend_for_root(root: Path) -> None:
        templates_root = root / "templates"
        candidates.extend(
            [
                root / slug,
                root / package_name,
                root / distribution_name / package_name,
                root / distribution_name,
                templates_root / slug,
                templates_root / package_name,
                templates_root / distribution_name / package_name,
                templates_root / distribution_name,
            ]
        )

    cwd = Path.cwd().resolve()
    visited_roots: set[Path] = set()
    current = cwd
    while current not in visited_roots:
        visited_roots.add(current)
        _extend_for_root(current)
        if current.parent == current:
            break
        current = current.parent

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        yield candidate


__all__ = [
    "copy_template_assets",
    "load_template",
]
