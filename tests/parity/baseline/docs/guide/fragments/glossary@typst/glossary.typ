#set document(
  title: "Glossary",
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
  #text(size: 1.8em, weight: "bold")[Glossary]
]
#v(1.5em)

In online documentation, a glossary doesn't make much sense because you can
search for terms directly and you have hyperlinks. However, in printed documents, a
glossary can be very useful to provide definitions of terms used in the text.

TeXSmith adds support for glossaries through the `glossary` extension, which
allows you to define glossary entries in your Markdown files and generate a
glossary section in the output document.

The fragment is automatically included when needed:

- If you use acronyms or abbreviations.
- If you define glossary entries using the `glossary` directive.
