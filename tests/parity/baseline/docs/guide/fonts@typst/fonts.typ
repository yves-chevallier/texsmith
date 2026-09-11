#set document(
  title: "Fonts and scripts",
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
  #text(size: 1.8em, weight: "bold")[Fonts and scripts]
]
#v(1.5em)

TeXSmith automatically wraps non‑Latin scripts in moving arguments (headings, captions, index entries, …) with per‑script font macros, using a cached lookup built from the Noto family. This gives fast, consistent multilingual output without manual fontspec boilerplate.

= Inspect detected fallback fonts

Use the render command with `--fonts-info` to display the scripts and fonts that were detected during a build. The flag works for both direct LaTeX output and full template renders:

```bash
uv run texsmith examples/dialects/dialects.md --template article --fonts-info
```

The report includes:

- the script name and the generated LaTeX commands (`\text<slug>` / `\<slug>font`);
- the font family chosen for that script (from the cached fallback index);
- the number of codepoints seen for that script in the current render.

When Rich is available, the information is shown as a table; otherwise a plaintext list is printed. The option is non-intrusive and does not change the output artefacts.
