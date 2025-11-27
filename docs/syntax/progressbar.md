# Progress Bars

The `texsmith.progressbar` extension mirrors the [`pymdownx.progressbar`][pymdownx] syntax and
converts it into LaTeX commands powered by the
[`progressbar`](https://ctan.org/pkg/progressbar) package. It is enabled by default, so you can
drop the `[=75% "Done"]` shorthand in your Markdown and keep both the HTML preview and the PDF build in sync.

## Syntax

````markdown
[=25% "Research"]
[=50% "Implementation"]
[=75% "Review"]
[=100% "Launch"]{: .thin}
````

- Values must be percentages (`0 – 100`). TexSmith clamps the values if needed.
- The quoted label is optional; when omitted the percentage is used.
- Trailing attribute lists (`{: .class #id }`) attach CSS classes and HTML attributes.
  Use the `.thin` class to halve the bar height (e.g. for tables or dense summaries).

## LaTeX output

During rendering, TeXSmith emits a `\progressbar` call with the following defaults:

```latex
{\progressbar[
  width=9cm,
  heighta=12pt,
  roundnessr=0.1,
  borderwidth=1pt,
  linecolor=black,
  filledcolor=black!60,
  emptycolor=black!10
]{0.73} Launch}
```

The `.thin` class switches `heighta` to `6pt`. If you need more control, wrap the Markdown block
in a raw LaTeX fence and tweak the options directly.

## Example project

Use the bundled `examples/progressbar` project for smoke tests or screenshots:

```bash
cd examples/progressbar
texsmith progressbar.md --template article --output-dir build --build
```

````md { .snippet }
[=25% "Research"]
[=50% "Implementation"]
[=75% "Review"]
[=100% "Launch"]{: .thin}
````



[pymdownx]: https://facelessuser.github.io/pymdown-extensions/extensions/progressbar/
