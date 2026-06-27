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

## Shipping readers & writers in a template

When custom constructs belong to a specific **template** (an exam, a thesis, a
poster…), declare the reader modules and the writer subclass in that template's
`[latex.template]` manifest section. TeXSmith resolves them when the template is
selected and applies them to the renderer **for that template only** — other
templates keep the default bundled read→write path.

```toml
[latex.template]
name = "exam"
version = "1.0.0"
entrypoint = "template/template.tex"
engine = "lualatex"

# Modules whose @reads lowerings are layered on top of the bundled registry.
# A higher-priority handler may return NotHandled to fall through to a core one.
readers = ["my_exam_pkg.reader"]

# A "module:Class" reference to a LaTeXWriter subclass adding/overriding @writes.
writer = "my_exam_pkg.writer:ExamLaTeXWriter"
```

- **`readers`** — a list of importable module paths. Every `@reads`-decorated
  callable found in each module is registered, layered on top of the bundled
  HTML→IR lowerings (`texsmith.readers.html.build_reader_registry`).
- **`writer`** — a `"module:Class"` reference to a `LaTeXWriter` subclass. It is
  validated at render time (must subclass `LaTeXWriter`), then used as the
  template's writer so its `@writes` emitters and overrides take effect.

Both are resolved with the same import machinery as attribute normalisers and
fragment entrypoints, so a typo or a bad reference fails early with an
actionable `TemplateError`. A template that declares neither is unaffected.

!!! note "Scope"
    These hooks are **template-scoped by design**. Because exam-style rules
    (e.g. mapping every `h1` to `\question`) would corrupt unrelated documents,
    they are never registered globally — only while the declaring template
    renders. There is no global reader/writer entry point.

Inside an extension, read template front-matter overrides from
`self.state.runtime["template_overrides"]` (already populated by the pipeline);
keep cross-node state on `self.state.state` (the `DocumentState`) and harvest it
in a pre-pass over the IR (`texsmith.ir.visitor.walk`) rather than mutating
shared state during emission.

## Reference

::: texsmith.readers.html.registry

::: texsmith.readers.html.reader

::: texsmith.writers.latex
