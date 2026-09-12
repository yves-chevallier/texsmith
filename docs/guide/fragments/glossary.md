# Glossary

In online documentation, a glossary doesn't make much sense because you can
search for terms directly and you have hyperlinks. However, in printed documents, a
glossary can be very useful to provide definitions of terms used in the text.

TeXSmith supports glossaries through the `ts-glossary` fragment: declare the
entries in the front matter under `press.declare.glossary` (and the acronyms
under `press.declare.acronyms`, or inline with `*[KEY]: …`), and the fragment
loads `glossaries`, declares every entry and prints the backmatter.

Nothing has to be enabled by hand. The fragment is activated by the writer,
which names it in `Requires.fragments` as soon as a body emits `\tsgls` or
`\tsacr` — that is, as soon as the document actually uses a glossary term or an
acronym. A document that declares none carries no `ts-glossary.sty`.

`\tsgls{key}` is `\gls` (the first use expands, later ones use the short form);
`\tsacr{key}` is `\acrshort`, the short form wherever it stands.

The declaration syntax, the groups and the sorting rules are in
[YAML Front Matter](../front-matter.md#glossary).
