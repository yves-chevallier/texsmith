# TeXSmith TeXlogos

An small TeXSmith extension that provides rich HTML rendering and LaTeX output for the classic logo commands: `\TeX`, `\LaTeX`, `\LaTeXe`, et `\TeX{}\textsc{Smith}`.

## Features

- Markdown extension that converts logo names into accessible HTML spans with tooltips.
- LaTeX renderer hooks that emit the canonical logo commands in the final document.
- MkDocs demo site showing what the logos look like in HTML when the extension is enabled.

## Usage

```bash
uv pip install texsmith-texlogos
```

Enable the Markdown extension:

```toml
[texsmith.extensions]
markdown_extensions = ["texsmith_texlogos"]
```

Or directly in Python:

```python
from markdown import Markdown
from texsmith_texlogos.markdown import TexLogosExtension

md = Markdown(extensions=[TexLogosExtension()])
html = md.convert("TeX and LaTeX2ε are handled automatically.")
```

To register the renderer hooks:

```python
from texsmith.adapters.latex.renderer import LaTeXRenderer
from texsmith_texlogos import register_renderer

renderer = LaTeXRenderer()
register_renderer(renderer)
```

The renderer registration works for both the CLI and programmatic APIs.
