# Readers & Writers

TeXSmith converts a document through a typed intermediate representation (IR):

```
read(HTML) → IR (texsmith.ir) → write(IR) → LaTeX
```

A **reader** lowers BeautifulSoup nodes into backend-agnostic IR nodes, and a
**writer** emits a backend (LaTeX) from that IR. Custom constructs are added in
two halves that mirror how the built-in constructs work.

## Reader lowerings — `@reads`

A reader lowering is a callable decorated with `@reads(*tags, level, priority,
name)`. It **returns** an IR node (never mutates the tree). Returning
`NotHandled` lets the next candidate — or the generic fallback — run.

```python
from bs4 import Tag

from texsmith.ir import nodes as ir
from texsmith.readers.html.registry import NotHandled, ReadLevel, reads


@reads("span", level=ReadLevel.INLINE, name="data_counter", priority=50)
def read_data_counter(tag: Tag, ctx) -> ir.Span | object:
    classes = tag.get("class") or []
    tokens = {classes} if isinstance(classes, str) else set(classes)
    if "data-counter" not in tokens:
        return NotHandled
    return ir.Span(content=(), attrs=(("role", "counter"),))
```

## Writer emitters — `@writes`

A writer emitter is a method decorated with `@writes(NodeType)` on a
`LaTeXWriter` subclass. Dispatch is typed by node class via the MRO; a node
without an emitter raises a clear `LaTeXWriteError`.

```python
from texsmith.ir import nodes as ir
from texsmith.writers.latex import LaTeXWriter, writes


class CountingWriter(LaTeXWriter):
    @writes(ir.Span)
    def _counter_span(self, node: ir.Span) -> str:
        if dict(node.attrs).get("role") == "counter":
            value = self.state.state.next_counter("data-counter")
            return f"\\counter{{{value}}}"
        return super()._span(node)
```

See [`examples/custom-render/counter.py`](https://github.com/texsmith/texsmith/blob/main/examples/custom-render/counter.py)
for a complete, runnable extension wiring both halves into a `LaTeXRenderer`.

!!! tip
    Keep the IR semantic and backend-neutral: encode hints via `Span`/`Div`
    `attrs` (e.g. `("role", "counter")`) rather than backend strings. Only the
    writer knows about LaTeX.

## Reference

::: texsmith.readers.html.registry

::: texsmith.readers.html.reader

::: texsmith.writers.latex
