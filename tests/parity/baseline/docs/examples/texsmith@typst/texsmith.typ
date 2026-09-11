#set document(
  title: "TeXSmith",
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
  #text(size: 1.8em, weight: "bold")[TeXSmith]
]
#v(1.5em)

And of course, the grand finale—the true climax of the project—is that this very documentation can itself be converted into a LaTeX document using TeXSmith.

```bash
git clone https://github.com/yves-chevallier/texsmith.git
cd texsmith
uv sync --with docs
export TEXSMITH_MKDOCS_BUILD=1 # Enable PDF build
uv run texsmith mkdocs build
```

You can download it directly from the #link("https://github.com/yves-chevallier/texsmith/releases")[release page].
