"""Example counter extension built on top of texsmith."""

from __future__ import annotations

from texsmith import DocumentState, LaTeXRenderer, RenderPhase, renders


COUNTER_CLASS = "data-counter"
COUNTER_KEY = "data-counter"


@renders("span", phase=RenderPhase.INLINE, name="inline_data_counter")
def render_data_counter(element, context) -> None:
    """Replace ``<span class=\"data-counter\">`` nodes with an incrementing marker."""

    classes = element.get("class") or []
    if isinstance(classes, str):
        tokens = {classes}
    else:
        tokens = set(classes)
    if COUNTER_CLASS not in tokens:
        return

    counter_value = context.state.next_counter(COUNTER_KEY)
    element.replace_with(f"\\counter{{{counter_value}}}")


def build_renderer() -> LaTeXRenderer:
    """Instantiate the renderer with the counter extension registered."""

    renderer = LaTeXRenderer()
    renderer.register(render_data_counter)
    return renderer


HTML = r"""
<h1>Counter Example</h1>

<p>
This is item <span class="data-counter"></span> but we can also have another
item <span class="data-counter"></span> and even more <span class="data-counter"></span>.
</p>
"""


__all__ = [
    "COUNTER_CLASS",
    "COUNTER_KEY",
    "HTML",
    "build_renderer",
    "render_data_counter",
]


state = DocumentState()
renderer = build_renderer()
print(renderer.render(HTML, state=state))
