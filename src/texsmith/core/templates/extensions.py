"""Resolve a template's render-extension hooks (custom readers / writer).

A template package can extend the LaTeX conversion pipeline for *its own*
documents by declaring, in its ``[latex.template]`` manifest section:

* ``readers`` — a list of importable module paths whose ``@reads`` lowerings are
  layered on top of the bundled HTML→IR registry;
* ``writer`` — a ``"module:Class"`` reference to a :class:`LaTeXWriter` subclass
  that adds or overrides ``@writes`` emitters.

These hooks are **scoped to the selected template**: they are applied to the
``LaTeXRenderer`` only while that template is rendering, so installing an
exam/thesis/… template never changes how other templates convert.

The resolution reuses the same ``"module:attribute"`` import machinery as
attribute normalisers and fragment entrypoints, so misconfiguration fails early
with an actionable :class:`TemplateError`.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from .manifest import TemplateError, _import_object


if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from texsmith.adapters.latex.renderer import LaTeXRenderer
    from texsmith.writers.latex.writer import LaTeXWriter


def resolve_reader_modules(paths: Iterable[str]) -> list[object]:
    """Import each module path, raising ``TemplateError`` on failure."""
    modules: list[object] = []
    for path in paths:
        if not isinstance(path, str) or not path.strip():
            raise TemplateError(f"Invalid template reader module reference: {path!r}.")
        try:
            modules.append(import_module(path.strip()))
        except ImportError as exc:
            raise TemplateError(
                f"Template reader module '{path}' could not be imported: {exc}."
            ) from exc
    return modules


def resolve_writer_class(reference: str) -> type[LaTeXWriter]:
    """Import and validate a ``"module:Class"`` LaTeXWriter subclass reference."""
    from texsmith.writers.latex.writer import LaTeXWriter

    obj = _import_object(reference, allow_dotted=True)
    if not (isinstance(obj, type) and issubclass(obj, LaTeXWriter)):
        raise TemplateError(
            f"Template writer '{reference}' must resolve to a LaTeXWriter subclass, "
            f"got {obj!r}."
        )
    return obj


def apply_render_extensions(
    renderer: LaTeXRenderer,
    *,
    readers: Sequence[str] | None,
    writer: str | None,
) -> None:
    """Populate ``renderer`` with a template's custom readers and/or writer.

    A no-op when the template declares neither, keeping the default
    bundled-only read→write path untouched.
    """
    if readers:
        from texsmith.readers.html import build_reader_registry

        renderer.reader_registry = build_reader_registry(resolve_reader_modules(readers))
    if writer:
        renderer.writer_class = resolve_writer_class(writer)


__all__ = [
    "apply_render_extensions",
    "resolve_reader_modules",
    "resolve_writer_class",
]
