#set document(
  title: "Smarty Pants",
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
  #text(size: 1.8em, weight: "bold")[Smarty Pants]
]
#v(1.5em)

This extension ports the Python-Markdown SmartyPants behavior. It swaps
plain ASCII punctuation for typographically “smart” equivalents—straight quotes
become curly quotes, `--` becomes an en dash, and `---` turns into an em dash.
The substitutions happen in both HTML and LaTeX output, so your prose looks
polished everywhere.
