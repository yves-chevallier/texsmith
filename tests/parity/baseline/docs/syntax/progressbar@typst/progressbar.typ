#set document(
title: "Progress Bars",
)
#set page(
paper: "a4",
margin: 2.5cm,
numbering: none,
footer: context {
if counter(page).final().first() > 1 {
align(center)[#counter(page).get().first()]
}
},
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
#text(size: 1.8em, weight: "bold")[Progress Bars]]
#v(1.5em)

A progress bar is an inline node with a value and an optional label. The
spelling is PyMdownX's and is the canonical one, so the HTML preview and the
PDF build stay in sync out of the box; in print it becomes a `\tsprogress`
call from the `ts-typesetting` fragment, over the
#link("https://ctan.org/pkg/progressbar")[`progressbar`] package.

= Syntax

```markdown
[=25% "Research"]
[=50% "Implementation"]
[=75% "Review"]
[=100% "Launch"]{.thin}
```

- Values must be percentages (`0 – 100`). TeXSmith clamps the values if needed.
- The quoted label is optional; when omitted the percentage is used.
- A trailing attribute list (`{.class #id}`) attaches on any host. Use the
`.thin` class to halve the bar height (e.g. for tables or dense summaries);
other classes reach the web stylesheet and are ignored in print.
- The bar is *inline*, so it fits in a table cell. Consecutive bars on
separate lines are separate paragraphs or hard-broken lines, and the template
chooses the width.
- The fraction form `[=9/20 "Review"]` and the `{: .thin}` attribute spelling
are deprecated sugar, normalised by `tmark lint –fix`; see
Migrating to TMark.

= #ts-logo("LaTeX") output

The writer emits `\tsprogress[thin]{0.45}{label}`; the fragment expands it to a
`\progressbar` call with the following defaults:

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

The `.thin` class switches `heighta` to `6pt`. For more control, redefine
`\tsprogress` in your template or append to its `pgfkeys` family.

= Example project

Use the bundled `examples/progressbar` project for smoke tests or screenshots:

```bash
cd examples/progressbar
texsmith progressbar.md --template article --output-dir build --build
```

#figure(
image("snippet-<HASH>.png"),
)
