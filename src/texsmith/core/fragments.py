"""Pluggable fragment helpers (templated .sty packages)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from texsmith.core.templates.base import _build_environment
from texsmith.core.templates.manifest import TemplateError


@dataclass(slots=True)
class Fragment:
    """Resolved fragment template ready to render."""

    name: str
    template_path: Path


_BUILTIN_FRAGMENTS: dict[str, Path] = {
    "ts-fonts": Path(__file__).resolve().parent.parent
    / "builtin_templates"
    / "common"
    / "ts-fonts.sty.jinja",
    "ts-callouts": Path(__file__).resolve().parent.parent
    / "builtin_templates"
    / "common"
    / "ts-callouts.sty.jinja",
    "ts-code": Path(__file__).resolve().parent.parent
    / "builtin_templates"
    / "common"
    / "ts-code.jinja.tex",
    "ts-glossary": Path(__file__).resolve().parent.parent
    / "builtin_templates"
    / "common"
    / "ts-glossary.sty.jinja",
}


def register_fragment(name: str, path: Path) -> None:
    """Register a custom fragment path (mainly for extensions/tests)."""
    _BUILTIN_FRAGMENTS[name] = path


def _resolve_fragment(name: str, *, source_dir: Path | None = None) -> Fragment:
    candidate: Path | None = None
    if name in _BUILTIN_FRAGMENTS:
        candidate = _BUILTIN_FRAGMENTS[name]
    else:
        path_candidate = Path(name)
        if not path_candidate.is_absolute() and source_dir is not None:
            path_candidate = (source_dir / path_candidate).resolve()
        candidate = path_candidate
    if candidate is None or not candidate.exists():
        raise TemplateError(f"Fragment '{name}' could not be resolved.")
    return Fragment(name=Path(name).stem, template_path=candidate)


def render_fragments(
    names: Iterable[str],
    *,
    context: Mapping[str, Any],
    output_dir: Path,
    source_dir: Path | None = None,
) -> tuple[list[str], list[Path]]:
    """
    Render the selected fragments into ``output_dir`` and return the package names.
    """
    rendered_packages: list[str] = []
    written: list[Path] = []
    for name in names:
        fragment = _resolve_fragment(name, source_dir=source_dir)
        env = _build_environment(fragment.template_path.parent)
        template = env.get_template(fragment.template_path.name)
        payload = template.render(**context)
        fragment_name = fragment.name
        output_path = output_dir / f"{fragment_name}.sty"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        rendered_packages.append(fragment_name)
        written.append(output_path)
    return rendered_packages, written


__all__ = ["Fragment", "register_fragment", "render_fragments"]
