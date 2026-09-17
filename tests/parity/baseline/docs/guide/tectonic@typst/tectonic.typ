#set document(
title: "Tectonic Engine",
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
#text(size: 1.8em, weight: "bold")[Tectonic Engine]]
#v(1.5em)

#ts-callout-style.update("fancy")

Tectonic is the default PDF engine in TeXSmith. It bundles automatic package
fetching, fast incremental builds, and minimal setup – ideal for CI pipelines and
lightweight containers. You can switch to `latexmk` with `–engine lualatex` or
`–engine xelatex` when you need full control of the traditional toolchain.

= Install Tectonic

- *macOS:* `brew install tectonic`
- *Ubuntu/Debian:* `sudo apt install tectonic` (or `cargo install tectonic`)
- *Fedora:* `sudo dnf install tectonic`
- *Windows:* `scoop install tectonic` or `choco install tectonic`
- *Fallback:* grab a prebuilt archive from #link("https://tectonic-typesetting.github.io/") and put
the `tectonic` binary on your `PATH`.

After installation, run `tectonic –version` to confirm the binary is available.

= Building with Tectonic

- CLI: `texsmith notes.md –template article –build` uses Tectonic automatically.
- Latexmk: add `–engine lualatex` (or `–engine xelatex`) to opt into the latexmk +
`.latexmkrc` flow.
- API: call `ConversionService.build_pdf(render_result, engine="tectonic")` after
rendering a template.

TeXSmith still checks for optional helpers – `biber`, `makeindex`\/`texindy`,
`makeglossaries` – and reports anything missing before the engine runs.
