#set document(
  title: "Colorful Squares",
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
  #text(size: 1.8em, weight: "bold")[Colorful Squares]
]
#v(1.5em)

This example shows off a custom poster-ish template with four slots wired through a local template. Front matter steers colors, slot routing, and layout—no LaTeX tweaks needed.

The YAML front matter picks the locally defined template (`.`), sets the palette, and feeds each slot. Colors live under `colors`, and slot content under `slots`.

The manifest defines defaults, available attributes, and where they get injected.

```md

```

```toml

```

```tex

```

Build it with:

```
$ ls
colorful.md  manifest.toml  template.tex
$ texsmith colorful.md -t. --build
┌───────────────┬─────────────────────────────────────┐
│ Artifact      │ Location                            │
├───────────────┼─────────────────────────────────────┤
│ PDF           │ <STEM>.pdf                        │
└───────────────┴─────────────────────────────────────┘
```
