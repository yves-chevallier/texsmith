# Standalone Plugins

Some ideas on standalone plugins that can be developed and shared independently or included in TeXSmith by default. These are some features that I can use myself and that can be useful to others.

## Epigraph

Integrate epigraph support via a dedicated plugin. The goal is to let users insert epigraphs easily from Markdown files. It can be declared as a fragment and declared in the document via front matter:

```yaml
epigraph: text
epigraph:
  quote: "To be, or not to be, that is the question."
  source: "William Shakespeare, Hamlet"
```

This is inserted into the LaTeX output using the `epigraph` package:

```latex
\usepackage{epigraph}
\setlength\epigraphwidth{0.6\textwidth}
\setlength\epigraphrule{0pt}
```

Then, at the desired location in the document:

```latex
\epigraph{To be, or not to be, that is the question.}{William Shakespeare, \textit{Hamlet}}
```

## SvgBob

This can be a good example of a standalone TeXSmith plugin that allows rendering ASCII art diagrams using Svgbob.

[Svgbob](https://github.com/ivanceras/svgbob) lets you sketch diagrams using ASCII art. Save the source with a `.bob` extension (or keep it inline) and link to it like any other image:

```markdown
![Sequence diagram](assets/pipeline.bob)
```

During the build TeXSmith calls the bundled Svgbob converter, generates a PDF, and inserts it into the final LaTeX output. Cached artifacts prevent repeated rendering when the source diagram stays the same.

SVGBob can be installed on Ubuntu via:

```bash
cargo install svgbob_cli
```

It is installed by default into `svgbob_cli` or `~/.cargo/bin/svgbob_cli`. We want to check both, warn if the binary is missing, and allow users to override the path via configuration.

We can insert the image in both ways:

````markdown
```svgbob
       +10-15V           ___0,047R
      *---------o-----o-|___|-o--o---------o----o-------.
    + |         |     |       |  |         |    |       |
    -===-      _|_    |       | .+.        |    |       |
    -===-      .-.    |       | | | 2k2    |    |       |
    -===-    470| +   |       | | |        |    |      _|_
    - |       uF|     '--.    | '+'       .+.   |      \ / LED
      +---------o        |6   |7 |8    1k | |   |      -+-
             ___|___   .-+----+--+--.     | |   |       |
              -═══-    |            |     '+'   |       |
                -      |            |1     |  |/  BC    |
               GND     |            +------o--+   547   |
                       |            |      |  |`>       |
                       |            |     ,+.   |       |
               .-------+            | 220R| |   o----||-+  IRF9Z34
               |       |            |     | |   |    |+->
               |       |  MC34063   |     `+'   |    ||-+
               |       |            |      |    |       |  BYV29     -12V6
               |       |            |      '----'       o--|<-o----o--X OUT
 6000 micro  - | +     |            |2                  |     |    |
 Farad, 40V ___|_____  |            |--o                C|    |    |
 Capacitor  ~ ~ ~ ~ ~  |            | GND         30uH  C|    |   --- 470
                      |            |3      1nF         C|    |   ###  uF
               |       |            |-------||--.       |     |    | +
               |       '-----+----+-'           |      GND    |   GND
               |            5|   4|             |             |
               |             |    '-------------o-------------o
               |             |                           ___  |
               `-------------*------/\/\/------------o--|___|-'
                                     2k              |       1k0
                                                    .+.
                                                    | | 5k6 + 3k3
                                                    | | in Serie
                                                    '+'
                                                     |
                                                    GND
```
````

If Svgbob is not available, diagrams can be skipped with a warning and rendered as code blocks.

## CircuitTikZ

The [CircuitTikZ designer](https://circuit2tikz.tf.fau.de/designer/) helps produce circuit diagrams from the browser. Export the generated TikZ snippet and wrap it in a raw LaTeX fence:

````markdown
```latex raw
\begin{circuitikz}
    \draw (0,0) to[battery] (0,2)
          -- (3,2) to[R=R] (3,0) -- (0,0);
\end{circuitikz}
```
````

`latex raw` is the canonical spelling of a raw fence; `/// latex … ///` is read
as deprecated sugar for it and `tmark lint --fix` rewrites it. Raw blocks bypass
the HTML output but remain in the LaTeX build. To keep the TikZ code in a separate file, include it via `\input{}` inside a raw fence and store the `.tex` asset alongside the Markdown.

# Module Design Principles

Verify that TeXSmith respects these design principles:

- Modules can inject, extend, and redefine functionality.
- Modules remain deterministic through topological ordering.
- Modules foster reusability and remixing.
- Modules cooperate through well-defined contracts.

# Visual Tweaks

- Reduce line height for code that uses Unicode box characters.
- Critic markup is not lowered by the parser yet: `{++inserted++}`,
  `{--deleted--}`, `{~~old~~new~~}` and `{>>comment<<}` stay literal text and
  raise `compat-unsupported`, so the curly braces no longer leak silently —
  they are reported. The `ts-critic` fragment already defines `\tsins`,
  `\tsdel`, `\tssubst` and `\tscomment` over `ulem` and `xcolor`; restyle
  them by redefining the macros in your template, and revisit the colours once
  the writers emit them.

# Issues

## Markdown Package Issues

`mkdocstrings` autorefs define heading anchors via `[](){#id}`, which triggers Markdown lint violations. TMark reads the pair as the anchor it was meant to be (it used to produce an empty `\url{}` and lose the `\label`), reports it as `deprecated` and offers `[]{#id}` as the fix — which is the spelling to prefer once autorefs indexes it.
