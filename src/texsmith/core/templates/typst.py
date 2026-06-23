"""Typst-template loading and document wrapping.

This is the Typst counterpart of :mod:`texsmith.core.templates.base` /
:mod:`~texsmith.core.templates.wrapper`. The LaTeX wrapper carries a large
fragment/glossary/index-engine machinery that has no Typst equivalent; rather
than thread Typst through it, this module provides a *lean parallel path*:

1. Load a template's ``[typst.template]`` manifest section (raising if absent).
2. Build a Jinja environment using **standard** ``{{ }}`` / ``{% %}`` delimiters
   (Typst source uses ``#``/``$``/``\\VAR{}`` heavily, so the LaTeX-style
   delimiters are unsuitable here).
3. Resolve template attributes from front-matter overrides via the shared,
   backend-agnostic :class:`TemplateAttributeSpec` machinery.
4. Render ``template/template.typ`` with the resolved context + the Typst body
   produced by :class:`~texsmith.writers.typst.TypstWriter`.

It keeps SSOT with the LaTeX side by reusing :class:`TemplateManifest`,
:class:`TemplateInfo`, the manifest path resolution, and the attribute resolver;
only the rendering environment and the (much smaller) context are Typst-specific.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import shutil
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from .base import _resolve_manifest_path
from .manifest import TemplateError, TemplateInfo, TemplateManifest


_TYPST_BACKEND = "typst"


def _build_typst_environment(template_root: Path) -> Environment:
    """Build the Jinja environment used to render ``.typ`` scaffolding."""
    search_paths = [str(template_root)]
    common_dir = template_root.parent / "common"
    if common_dir.exists():
        search_paths.append(str(common_dir))
    return Environment(
        loader=FileSystemLoader(search_paths),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


class TypstTemplate:
    """A template loaded for the Typst backend.

    Only templates declaring a ``[typst.template]`` manifest section can be
    instantiated; otherwise :meth:`TemplateManifest.section` raises.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        if not self.root.exists():
            raise TemplateError(f"Template root does not exist: {self.root}")
        manifest_path = _resolve_manifest_path(self.root)
        self.manifest = TemplateManifest.load(manifest_path)
        self.info: TemplateInfo = self.manifest.section(_TYPST_BACKEND)
        self.environment = _build_typst_environment(self.root)

    # -- context + rendering ----------------------------------------------

    def resolve_attributes(self, overrides: Mapping[str, Any] | None) -> dict[str, Any]:
        """Resolve template attributes from front-matter overrides."""
        return self.info.resolve_attributes(overrides)

    def render(self, context: Mapping[str, Any]) -> str:
        """Render the Typst entrypoint with ``context``."""
        try:
            template = self.environment.get_template(self.info.entrypoint)
        except TemplateNotFound as exc:
            raise TemplateError(
                f"Typst template entry '{self.info.entrypoint}' is missing in {self.root}"
            ) from exc
        return template.render(dict(context))

    def copy_assets(self, output_dir: Path) -> list[Path]:
        """Copy declared (non-templated) assets into ``output_dir``."""
        written: list[Path] = []
        for destination, asset in self.info.assets.items():
            dest_path = (output_dir / destination).resolve()
            source = Path(asset.source)
            if not source.is_absolute():
                source = (self.root / source).resolve()
            if not source.exists():
                raise TemplateError(
                    f"Declared template asset '{asset.source}' is missing under {self.root}."
                )
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(source, dest_path)
            written.append(dest_path)
        return written


def load_typst_template(identifier: str) -> TypstTemplate:
    """Load a Typst template by name or filesystem path.

    Reuses the LaTeX loader's discovery (builtin / packaged / local / home) to
    locate the template *root*, then re-wraps it for the Typst backend.
    """
    from .loader import load_template

    root = load_template(identifier).root
    return TypstTemplate(root)


__all__ = ["TypstTemplate", "load_typst_template"]
