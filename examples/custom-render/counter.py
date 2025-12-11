from __future__ import annotations

# Example counter extension built on top of texsmith.
import sys

from bs4.element import Tag

from texsmith import DocumentState, RenderContext, RenderPhase, renders
from texsmith.adapters.latex import LaTeXRenderer


COUNTER_CLASS = "data-counter"
COUNTER_KEY = "data-counter"


@renders("span", phase=RenderPhase.INLINE, name="inline_data_counter")
def render_data_counter(element: Tag, context: RenderContext) -> None:
    """Replace ``<span class=\"data-counter\">`` nodes with an incrementing marker."""
    classes = element.get("class") or []
    tokens = {classes} if isinstance(classes, str) else set(classes)
    if COUNTER_CLASS not in tokens:
        return

    counter_value = context.state.next_counter(COUNTER_KEY)
    element.replace_with(f"\\counter{{{counter_value}}}")


def build_renderer() -> LaTeXRenderer:
    """Instantiate the renderer with the counter extension registered."""
    renderer = LaTeXRenderer()
    renderer.register(render_data_counter)
    return renderer


HTML = (
    "<h1>Counter Example</h1>\n"
    "<p>\n"
    'This is item <span class="data-counter"></span> but we can also have another\n'
    'item <span class="data-counter"></span> and even more <span class="data-counter"></span>.\n'
    "</p>\n"
)


__all__ = [
    "COUNTER_CLASS",
    "COUNTER_KEY",
    "HTML",
    "build_renderer",
    "render_data_counter",
]


if __name__ == "__main__":
    state = DocumentState()
    renderer = build_renderer()
    sys.stdout.write(renderer.render(HTML, state=state))
