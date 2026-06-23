# TeXSmith Extensions

TeXSmith ships its Markdown extensions directly inside the `texsmith`
distribution. Once `pip install texsmith` is done, you can import them either
via the `texsmith.extensions` registry or by using the extension modules
(`texsmith.extensions.smallcaps`, `texsmith.extensions.index`, ...).

Every extension follows the same structure:

- A Python-Markdown class or `makeExtension()` factory available as
  `texsmith.extensions.<name>`.
- Optional reader lowerings (`@reads`) and writer emitters (`@writes`) that
  teach the IR pipeline how to deal with the extra HTML nodes created by the
  Markdown layer (see [Readers & Writers](../api/handlers.md)).
- Optional MkDocs plugins that keep search indexes in sync.

## Built-in extensions

In order to align Markdown with LaTeX capabilities, TeXSmith provides the
following extensions under the `texsmith` namespace:

| Module                       | Purpose                                                              |
| ---------------------------- | -------------------------------------------------------------------- |
| `texsmith.extensions.smallcaps`         | `__text__` syntax mapped to `<span class="texsmith-smallcaps">`.     |
| `texsmith.extensions.latex_raw`         | `/// latex` fences and `{latex}[x]` inline snippets injected as hidden HTML. |
| `texsmith.extensions.latex_text`        | Styles the literal `LaTeX` token in running text.                    |
| `texsmith.extensions.missing_footnotes` | Warns about references to undefined footnotes.                       |
| `texsmith.extensions.multi_citations`   | Normalises `^[foo,bar]` blocks to footnotes.                         |
| `texsmith.extensions.mermaid`           | Inlines Mermaid diagrams pointed to by Markdown images.              |
| `texsmith.extensions.texlogos`          | Replaces TeX logo keywords with accessible HTML spans.               |
| `texsmith.extensions.index`             | Adds the `#[tag]` syntax, LaTeX index entries and an MkDocs plugin.  |

Inspect the registry programmatically if you want to discover the available
extensions dynamically:

```python
>>> from texsmith.extensions import available_extensions
>>> [spec.package_name for spec in available_extensions()]
['texsmith.index', 'texsmith.extensions.latex_raw', 'texsmith.extensions.latex_text', ...]
```

## Using the extensions with Python Markdown

Use the registry helper to instantiate an extension or import the shorthand
module directly:

```python
from markdown import Markdown
from texsmith.extensions import load_markdown_extension

extensions = [
    load_markdown_extension("smallcaps"),
    load_markdown_extension("texlogos"),
    load_markdown_extension("index"),
]
md = Markdown(extensions=extensions)
html = md.convert("`#[LaTeX]` renders a TeX logo and an index entry.")
```

If you prefer the explicit class names the following also works:

```python
from texsmith.extensions.index import TexsmithIndexExtension

md = Markdown(extensions=[TexsmithIndexExtension()])
```

## Register extensions in MkDocs

Once TeXSmith is installed you can reference the modules directly from
`mkdocs.yml`:

```yaml
markdown_extensions:
  - texsmith.index
  - texsmith.texlogos
  - texsmith.extensions.smallcaps
```

(`texsmith.index` and `texsmith.texlogos` are registered entry-point aliases for
`texsmith.extensions.index` / `texsmith.extensions.texlogos`.)

The index extension also publishes an MkDocs plugin that injects collected tags
into the `search_index.json`. Enable it next to the Markdown extension:

```yaml
plugins:
  - texsmith.index
```

When you use `mkdocs-texsmith` the plugin automatically appends both the
Markdown extension and the MkDocs plugin unless you disable it with the
`inject_markdown_extension` option.

## Integrating with the LaTeX renderer

TeXSmith renders through a typed IR: `read(HTML) → IR → write(IR) → LaTeX`.
Extensions that need LaTeX output add a reader lowering (`@reads`, HTML → IR)
and a writer emitter (`@writes`, IR → LaTeX) instead of mutating HTML. See
[Readers & Writers](../api/handlers.md) for the decorators and a complete,
runnable example (`examples/custom-render/counter.py`).

## Write your own extensions

You can create custom Markdown extensions that plug into TeXSmith's conversion
pipeline. Refer to the API documentation for details on
the extension points and how to register your extension with TeXSmith.

### Pipeline placement & precedence

- Markdown extensions run before slot extraction and fragment rendering; any HTML they emit flows through the same pipeline.
- Reader lowerings (`@reads`) are selected by `(level, tag)` and priority; the resulting IR is then emitted by writer emitters (`@writes`) dispatched on node type.
- Extensions should not override template partials directly—expose fragment partials or attributes instead so precedence stays transparent.
