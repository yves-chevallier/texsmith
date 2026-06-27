from __future__ import annotations

# Example counter extension built on top of texsmith's IR architecture.
#
# The pipeline is ``read(HTML) -> IR -> write(IR) -> LaTeX``. A custom construct
# is added in two halves:
#   * a *reader* lowering (``@reads``) that turns the custom HTML into an IR node
#     (here a generic ``Span`` carrying a ``role`` hint), and
#   * a *writer* emitter (``@writes``) that turns that IR node into LaTeX.
#
# This mirrors how the built-in constructs work and keeps the IR backend-agnostic.
import sys

from texsmith import DocumentState
from texsmith.adapters.latex import LaTeXRenderer
from texsmith.ir import nodes as ir
from texsmith.readers.html.reader import _build_registry
from texsmith.readers.html.registry import NotHandled, ReadLevel, reads
from texsmith.writers.latex import LaTeXWriter, writes


COUNTER_CLASS = "data-counter"
COUNTER_KEY = "data-counter"


@reads("span", level=ReadLevel.INLINE, name="data_counter", priority=50)
def read_data_counter(tag, ctx):  # noqa: ANN001, ANN201
    """Lower ``<span class="data-counter">`` into a counter ``Span`` hint."""
    classes = tag.get("class") or []
    tokens = {classes} if isinstance(classes, str) else set(classes)
    if COUNTER_CLASS not in tokens:
        return NotHandled
    return ir.Span(content=(), attrs=(("role", "counter"),))


class CountingWriter(LaTeXWriter):
    """A LaTeX writer extended with an incrementing ``\\counter{N}`` emitter."""

    @writes(ir.Span)
    def _counter_span(self, node: ir.Span) -> str:
        if dict(node.attrs).get("role") == "counter":
            value = self.state.state.next_counter(COUNTER_KEY)
            return f"\\counter{{{value}}}"
        return super()._span(node)


def build_renderer() -> LaTeXRenderer:
    """Instantiate the renderer wired with the counter reader + writer."""
    registry = _build_registry()
    definition = read_data_counter.__reader_rule__  # type: ignore[attr-defined]
    registry.register(definition.bind(read_data_counter))

    renderer = LaTeXRenderer(parser="html.parser")
    renderer.reader_registry = registry
    renderer.writer_class = CountingWriter
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
    "CountingWriter",
    "build_renderer",
    "read_data_counter",
]


if __name__ == "__main__":
    state = DocumentState()
    renderer = build_renderer()
    sys.stdout.write(renderer.render(HTML, state=state))
