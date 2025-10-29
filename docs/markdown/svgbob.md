# Diagram Converters

TeXSmith ships with several transformer strategies that turn light-weight text
diagram formats into publication-ready PDFs.

## Svgbob

[Svgbob](https://github.com/ivanceras/svgbob) lets you sketch diagrams using
ASCII art. Save the source with a `.bob` extension (or keep it inline) and link
to it like any other image:

```markdown
![Sequence diagram](assets/pipeline.bob)
```

During the build TeXSmith calls the bundled Svgbob converter, generates a PDF,
and inserts it in the final LaTeX output. Cached artefacts prevent repeated
rendering when the source diagram does not change.

## CircuitTikZ

[CircuitTikZ designer](https://circuit2tikz.tf.fau.de/designer/) is a handy way
to produce circuit diagrams from a browser. Export the generated TikZ snippet
and wrap it in a raw LaTeX fence:

```markdown
/// latex
\begin{circuitikz}
    \draw (0,0) to[battery] (0,2)
          -- (3,2) to[R=R] (3,0) -- (0,0);
\end{circuitikz}
///
```

The raw block bypasses the HTML output but is preserved in the LaTeX build. If
you prefer to keep the file separate, include it via `\input{}` in a raw fence
and store the `.tex` asset alongside your Markdown.

## Tips

- Keep diagram sources under version control so illustrations stay editable.
- When running on CI, ensure any external binaries required by custom
  transformers are installed before invoking `texsmith render --build`.
- Combine diagrams with the `figure` slot of your template for consistent
  placement and captions.
