"""Renderer hooks to convert TeX logo spans into LaTeX macros."""

from __future__ import annotations

from collections.abc import Mapping

from bs4 import NavigableString, Tag

from texsmith.adapters.handlers._helpers import gather_classes, mark_processed
from texsmith.core.context import RenderContext
from texsmith.core.rules import RenderPhase, renders

from .specs import LogoSpec, alias_mapping, iter_specs


_COMMAND_LOOKUP: Mapping[str, LogoSpec] = {spec.command: spec for spec in iter_specs()}
_SLUG_LOOKUP: Mapping[str, LogoSpec] = {spec.slug: spec for spec in iter_specs()}
_ALIAS_LOOKUP = alias_mapping()
_REGISTER_ATTR = "_texsmith_texlogos_registered"


@renders(
    "span",
    phase=RenderPhase.INLINE,
    priority=32,
    name="texsmith_tex_logo",
    nestable=False,
    auto_mark=False,
)
def render_tex_logo_span(element: Tag, context: RenderContext) -> None:
    """Process ``<span class="tex-logo">`` placeholders."""

    classes = gather_classes(element.get("class"))
    if "tex-logo" not in classes:
        return

    spec = _deduce_spec(element)
    if spec is None:
        return

    latex = mark_processed(NavigableString(spec.command))
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(latex)


def _deduce_spec(element: Tag) -> LogoSpec | None:
    command = element.get("data-tex-command")
    if command:
        spec = _COMMAND_LOOKUP.get(command)
        if spec:
            return spec

    slug = element.get("data-tex-logo")
    if slug:
        spec = _SLUG_LOOKUP.get(slug)
        if spec:
            return spec

    text = element.get_text(strip=True)
    if text:
        return _ALIAS_LOOKUP.get(text)

    return None


def register(renderer: object) -> None:
    """Convenience helper to register all logo handlers on a renderer."""

    register_callable = getattr(renderer, "register", None)
    if callable(register_callable):
        if getattr(renderer, _REGISTER_ATTR, False):
            return
        register_callable(render_tex_logo_span)
        setattr(renderer, _REGISTER_ATTR, True)
        return

    raise TypeError("Renderer object does not expose a 'register' method")


__all__ = ["register", "render_tex_logo_span"]
