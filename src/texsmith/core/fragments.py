"""Pluggable fragment helpers (templated .sty packages)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
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


class FragmentRegistry:
    """Central registry resolving fragment templates."""

    def __init__(self, *, root: Path, default_order: Sequence[str]) -> None:
        self._root = root
        self._default_order = list(default_order)
        self._fragments: dict[str, Path] = {}
        self._discover_builtins()

    @property
    def default_fragment_names(self) -> list[str]:
        return [name for name in self._default_order if name in self._fragments]

    def register_fragment(self, name: str, path: Path) -> None:
        self._fragments[name] = path

    def resolve(self, name: str, *, source_dir: Path | None = None) -> Fragment:
        candidate: Path | None
        if name in self._fragments:
            candidate = self._fragments[name]
        else:
            path_candidate = Path(name)
            if not path_candidate.is_absolute() and source_dir is not None:
                path_candidate = (source_dir / path_candidate).resolve()
            candidate = path_candidate
        if candidate is None or not candidate.exists():
            raise TemplateError(f"Fragment '{name}' could not be resolved.")
        return Fragment(name=self._package_name(name), template_path=candidate)

    def _discover_builtins(self) -> None:
        if not self._root.exists():
            return
        patterns = ("*.sty.jinja", "*.jinja.tex")
        for pattern in patterns:
            for path in sorted(self._root.glob(pattern)):
                name = self._package_name(path.name)
                if name not in self._fragments:
                    self._fragments[name] = path

    @staticmethod
    def _package_name(identifier: str) -> str:
        candidate = Path(identifier)
        name = candidate.name
        for suffix in (".sty.jinja", ".jinja.tex"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        return Path(name).stem


BUILTIN_FRAGMENT_ORDER = [
    "ts-fonts",
    "ts-callouts",
    "ts-code",
    "ts-glossary",
    "ts-index",
]

FRAGMENT_ROOT = Path(__file__).resolve().parent.parent / "builtin_templates" / "common"
FRAGMENT_REGISTRY = FragmentRegistry(root=FRAGMENT_ROOT, default_order=BUILTIN_FRAGMENT_ORDER)


def register_fragment(name: str, path: Path) -> None:
    """Register a custom fragment path (mainly for extensions/tests)."""
    FRAGMENT_REGISTRY.register_fragment(name, path)


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
        fragment = FRAGMENT_REGISTRY.resolve(name, source_dir=source_dir)
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


__all__ = ["Fragment", "FragmentRegistry", "FRAGMENT_REGISTRY", "register_fragment", "render_fragments"]
