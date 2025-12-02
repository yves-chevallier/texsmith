# TeXSmith Extensions

TeXSmith ships its Markdown extensions directly inside the `texsmith`
distribution. Once `pip install texsmith` is done you can import them either
via the `texsmith.extensions` registry or by using the convenience modules
(`texsmith.smallcaps`, `texsmith.index`, ...).

Every extension follows the same structure:

- A Python-Markdown class or `makeExtension()` factory available as
  `texsmith.<name>`.
- Optional renderer hooks (`register_renderer`) that teach the LaTeX backend
  how to deal with the extra HTML nodes created by the Markdown layer.
- Optional MkDocs plugins that keep search indexes in sync.

## Built-in extensions

In order to align Markdown with LaTeX capabilities, TeXSmith provides the
following extensions under the `texsmith` namespace:

| Module                       | Purpose                                                              |
| ---------------------------- | -------------------------------------------------------------------- |
| `texsmith.smallcaps`         | `__text__` syntax mapped to `<span class="texsmith-smallcaps">`.     |
| `texsmith.latex_raw` / `texsmith.rawlatex` | `/// latex` fences and `{latex}[x]` inline snippets injected as hidden HTML. |
| `texsmith.latex_text`        | Styles the literal `LaTeX` token in running text.                    |
| `texsmith.missing_footnotes` | Warns about references to undefined footnotes.                       |
| `texsmith.multi_citations`   | Normalises `^[foo,bar]` blocks to footnotes.                         |
| `texsmith.mermaid`           | Inlines Mermaid diagrams pointed to by Markdown images.              |
| `texsmith.texlogos`          | Replaces TeX logo keywords with accessible HTML spans.               |
| `texsmith.index`             | Adds the `#[tag]` syntax, LaTeX index handlers and an MkDocs plugin. |

Inspect the registry programmatically if you want to discover the available
extensions dynamically:

```python
>>> from texsmith.extensions import available_extensions
>>> [spec.package_name for spec in available_extensions()]
['texsmith.index', 'texsmith.latex_raw', 'texsmith.latex_text', ...]
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
from texsmith.index import TexsmithIndexExtension

md = Markdown(extensions=[TexsmithIndexExtension()])
```

## Register extensions in MkDocs

Once TeXSmith is installed you can reference the modules directly from
`mkdocs.yml`:

```yaml
markdown_extensions:
  - texsmith.index
  - texsmith.texlogos
  - texsmith.smallcaps
```

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

Extensions that need LaTeX output expose renderer hooks via
`register_renderer(renderer)`. TeXSmith calls those hooks during the CLI render
pipeline, but you can reuse them in your own scripts:

```python
from texsmith.adapters.latex import LaTeXRenderer
from texsmith.index import register_renderer

renderer = LaTeXRenderer()
register_renderer(renderer)
latex_output = renderer.render(html_fragment)
```

If you want every built-in extension to register its renderer hook, call
`texsmith.extensions.register_all_renderers(renderer)`.

## Write your own extensions

You can create custom Markdown extensions that plug into TeXSmith's conversion
pipeline. Refer to the API documentation for details on
the extension points and how to register your extension with TeXSmith.

### Pipeline placement & precedence

- Markdown extensions run before slot extraction and fragment rendering; any HTML they emit flows through the same pipeline.
- Renderer hooks execute in `RenderPhase` order (PRE → BLOCK → INLINE → POST); use the lowest required phase to keep transforms predictable.
- Extensions should not override template partials directly—expose fragment partials or attributes instead so precedence stays transparent. 
