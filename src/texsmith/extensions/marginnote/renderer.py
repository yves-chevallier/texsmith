r"""LaTeX renderer for ``<ts-marginnote>`` nodes.

Emits ``\marginnote{…}`` from the ``marginnote`` package (auto-loaded by the
``ts-extra`` fragment on detection). A ``data-side="l"`` attribute forces the
left margin by wrapping the call in a group that locally applies
``\reversemarginpar``; the group scopes the switch so subsequent notes fall
back to the document-wide default.

Runs in the ``INLINE`` phase with ``after_children=True`` so inline children
(``<strong>``, ``<em>``, ``<code>``, ``<a>``) have already been rewritten to
LaTeX by the time we read the text. A dedicated tag is used — rather than a
``<span>`` — to avoid colliding with the renderer's many generic ``<span>``
handlers, several of which declare ``nestable=False`` and would otherwise
suppress our own ``after_children`` dispatch.
"""

from __future__ import annotations

from bs4 import NavigableString, Tag

from texsmith.adapters.handlers._helpers import coerce_attribute, mark_processed
from texsmith.core.context import RenderContext
from texsmith.core.rules import RenderPhase, renders

from .markdown import MARGIN_NOTE_TAG


@renders(
    MARGIN_NOTE_TAG,
    phase=RenderPhase.INLINE,
    priority=50,
    name="texsmith_marginnote",
    nestable=False,
    auto_mark=False,
    after_children=True,
)
def render_marginnote(element: Tag, context: RenderContext) -> None:
    r"""Convert ``<ts-marginnote>`` into a ``\marginnote`` call."""
    text = element.get_text(strip=False).strip()
    if not text:
        context.mark_processed(element)
        context.suppress_children(element)
        element.decompose()
        return

    side = coerce_attribute(element.get("data-side"))
    latex = _compose_latex(text, side)

    replacement = mark_processed(NavigableString(latex))
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(replacement)


def _compose_latex(text: str, side: str | None) -> str:
    if side == "l":
        # Group scopes ``\reversemarginpar`` so only this note flips.
        return rf"{{\reversemarginpar\marginnote{{{text}}}}}"
    return rf"\marginnote{{{text}}}"


def register(renderer: object) -> None:
    """Register the margin-note handler with the shared renderer."""
    register_callable = getattr(renderer, "register", None)
    if not callable(register_callable):
        raise TypeError("Renderer does not expose a 'register' method.")
    if getattr(renderer, "_texsmith_marginnote_registered", False):
        return
    register_callable(render_marginnote)
    renderer._texsmith_marginnote_registered = True  # noqa: SLF001


__all__ = ["register", "render_marginnote"]
