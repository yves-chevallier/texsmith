# Code listings

TeXSmith bundles a single fragment, `ts-code`, that can render fenced code blocks with four different engines:

`pygments` (default)
: highlights code with Pygments at render time and injects the generated macros into `ts-code.sty`. No shell escape is required and the output works with XeLaTeX and Tectonic. Not suited for editing the LaTeX output directly.

`listings`
: uses the LaTeX `listings` package inside a `tcolorbox`. Good for pure LaTeX workflows without shell escape, but no automatic line highlighting.

`verbatim`
: plain `fvextra`/`Verbatim` output wrapped in a tcolorbox. Useful when you want zero styling or external dependencies.

`minted`
: Enhanced version of listings that shells out to `pygmentize`. This needs `--shell-escape` and is disabled by default for compatibility with sandboxed engines such as Tectonic.

## Choosing an engine

If you have require to use one, pick the engine in front matter or via the CLI template override:

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

This engine is the most flexible and works with all TeX engines supported by TeXSmith, including Tectonic.

Furthermore, it is much faster than `minted` since it avoids shelling out during LaTeX compilation.

## Shell-escape behaviour

Shell escape is requested automatically when the minted engine is active or other features need it. With `pygments`, `listings`, or `verbatim`, `.latexmkrc` will not add `--shell-escape`, keeping builds compatible with engines like Tectonic.

!!! note

    By default TeX disables shell escape for security reasons. Only enable it if you trust the source of your documents. Shell escape allows LaTeX to run arbitrary commands on your system during compilation. This behaviour is strongly discouraged by Tectonic team and disabled by default.
