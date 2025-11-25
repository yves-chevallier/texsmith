# Code listings

TeXSmith bundles a single fragment, `ts-code`, that can render fenced code blocks with four different engines:

- `pygments` (default): highlights code with Pygments at render time and injects the generated macros into `ts-code.sty`. No shell escape is required and the output works with Tectonic.
- `listings`: uses the LaTeX `listings` package inside a `tcolorbox`. Good for pure LaTeX workflows without shell escape, but no automatic line highlighting.
- `verbatim`: plain `fvextra`/`Verbatim` output wrapped in a tcolorbox. Useful when you want zero styling or external dependencies.
- `minted`: mirrors the previous behaviour and shells out to `pygmentize`. This needs `--shell-escape` and is disabled by default for compatibility with sandboxed engines.

## Choosing an engine

Pick the engine in front matter or via the CLI template override:

```yaml
---
press:
  code:
    engine: listings  # verbatim | listings | minted | pygments
---
```

```bash
texsmith input.md -a code.engine=verbatim
```

The choice is global for a render. Inline code only uses `minted` when the engine is set to `minted`; otherwise it falls back to `\texttt{…}`.

## Pygments pipeline details

When `code.engine=pygments`, TeXSmith runs Pygments during conversion and writes the highlighted LaTeX directly into the `code` environment. All required style definitions are collected once per render and injected into `ts-code.sty`, so no external calls are made during LaTeX compilation. Highlighted lines and line numbers from the Markdown source are preserved.

## Shell-escape behaviour

Shell escape is requested automatically when the minted engine is active or other features need it. With `pygments`, `listings`, or `verbatim`, `.latexmkrc` will not add `--shell-escape`, keeping builds compatible with engines like Tectonic.
