#set document(
  title: "About",
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
  #text(size: 1.8em, weight: "bold")[About]
]
#v(1.5em)

TeXSmith was originally created by Yves Chevallier in 2025 to address the need for a seamless workflow between Markdown-based documentation and LaTeX-based publishing, initially for his own academic #link("https://heig-tin-info.github.io/handbook/")[courses] at HEIG-VD.

Aside from #link("https://pandoc.org/")[Pandoc]—written in #link("https://en.wikipedia.org/wiki/Haskell")[Haskell] and not directly suited for #link("https://www.mkdocs.org/")[MkDocs]—there were no tools capable of converting MkDocs-flavored Markdown into LaTeX while preserving the original content’s semantic intent.

Because developing such an ambitious toolchain was a substantial and time-consuming effort, I postponed the project until I discovered the remarkable power of OpenAI Codex, which helped me bootstrap the initial version of TeXSmith in just a few days. I wanted to extract the core MkDocs-to-LaTeX code used in my online course and turn it into a standalone, general-purpose tool that anyone needing to convert MkDocs content to LaTeX could use. That is how TeXSmith was born.

= Branding

This project is *not affiliated with TeX, LaTeX, or the LaTeX Project*. It merely produces LaTeX-compatible output and interacts with the TeX toolchain in the same way any document-generation utility would. All trademarks belong to their respective owners.

By convention within the TeX community, the names _TeX_ and _LaTeX_ are used with care. #link("https://en.wikipedia.org/wiki/Donald_Knuth")[Donald Knuth] famously stated:

#quote(block: true)[
  *“TeX is not to be changed; only Knuth himself may change TeX.”*
]

This is not a legal trademark declaration but a long-standing cultural rule: any system that calls itself _TeX_ must be fully compatible with Knuth’s canonical implementation. Similarly, the LaTeX Project requires that only implementations conforming to the LaTeX format may use the name _LaTeX_.

In keeping with these established norms, this project does *not* claim to be a TeX or LaTeX implementation, nor does it modify or replace them. It is simply a tool that _generates_ LaTeX code as output, leaving the actual typesetting to standard, community-maintained engines.
