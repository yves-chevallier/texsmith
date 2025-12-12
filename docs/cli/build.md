# Build

To build your LaTeX document into a PDF, use the `--build` (or `-b`) option. This command compiles the generated LaTeX file using the default engine. TeXSmith uses `tectonic` by default as it is the only self-contained LaTeX engine, but you can configure it to use `lualatex` or `xelatex` via `latexmk` if preferred. Here the example of a simple document built with different engines:

```bash
$ uv run texsmith cheese.md cheese.bib -tarticle --build --engine=xelatex
$ uv run texsmith cheese.md cheese.bib -tarticle --build --engine=lualatex
$ uv run texsmith cheese.md cheese.bib -tarticle --build --engine=tectonic
```
