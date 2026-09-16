# Livre français

A small French book — parts, chapters, sections, a table and accented text —
built with the `book` template and `language: fr`.

Babel's French names the parts with an ordinal built from the `part` counter
(`Première partie`, `Deuxième partie`), which the template's `fixtoc` package
has to measure when it sizes the table-of-contents number columns. This example
is the regression guard for that path: it is the corpus entry `book-fr`.
