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

If you need to use one, pick the engine in front matter or via the CLI template override:

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

The choice is global for a render. Inline code spans follow the engine too: `pygments` highlights them in place, `minted` wraps them in `\mintinline`, and `listings`/`verbatim` fall back to plain `\texttt{…}`.

## Inline code wrapping

A fenced block always wraps: every engine is configured with `breaklines` (and `breakanywhere` for `fvextra`), so a long line folds inside the box instead of running past it. An *inline* span has no such luxury — it sits in a justified paragraph and TeX will not break it on its own, so a long identifier such as `texsmith.core.conversion_options` pushes into the margin.

The `code.inline` section declares where such a span may break:

```yaml
---
press:
  code:
    inline:
      plain: true          # typeset inline code as plain \texttt, no highlighting
      breaks: "_./"        # insert a break opportunity after each of these characters
---
```

`breaks`
: The characters after which an `\allowbreak` is inserted. Defaults to `-`, which is what TeXSmith has always done. Use `all` (or `true`) for the full punctuation set `-_./\:;,|@+=&#%`, and `none` (or `false`) to disable breaking entirely. Letters, digits and whitespace are ignored: breaking mid-word hurts legibility more than a slight overflow. Breaks are inserted in highlighted spans too, between the Pygments macros rather than inside them, so the colours survive.

`plain`
: When true, inline spans are rendered as `\texttt{…}` with no syntax colouring, whatever the engine — the "simple mono" mode. Blocks keep their highlighting. This is the only way to get break opportunities under the `minted` engine, whose `\mintinline` is verbatim and cannot host an `\allowbreak`; and a document that only has inline spans no longer requests the shell escape `\mintinline` would have needed.

Both keys work as CLI overrides as well:

```bash
texsmith input.md -a code.inline.plain=true -a code.inline.breaks=_./
```

## Pygments pipeline details

When `code.engine=pygments`, TeXSmith runs Pygments during conversion and writes the highlighted LaTeX directly into the `code` environment. All required style definitions are collected once per render and injected into `ts-code.sty`, so no external calls are made during LaTeX compilation. Highlighted lines and line numbers from the Markdown source are preserved.

This engine is the most flexible and works with all TeX engines supported by TeXSmith, including Tectonic.

Furthermore, it is much faster than `minted` since it avoids shelling out during LaTeX compilation.

## Shell-escape behavior

Shell escape is requested automatically when the minted engine is active or other features need it. With `pygments`, `listings`, or `verbatim`, `.latexmkrc` will not add `--shell-escape`, keeping builds compatible with engines like Tectonic.

!!! note

    By default TeX disables shell escape for security reasons. Only enable it if you trust the source of your documents. Shell escape allows LaTeX to run arbitrary commands on your system during compilation. This behavior is strongly discouraged by the Tectonic team and disabled by default.
