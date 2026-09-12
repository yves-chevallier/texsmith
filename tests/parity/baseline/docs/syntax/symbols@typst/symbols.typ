#set document(
title: "Smart symbols and quotes",
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
#text(size: 1.8em, weight: "bold")[Smart symbols and quotes]]
#v(1.5em)

Two substitutions run while TMark scans a run of text: the smart symbols of
`pymdownx.smartsymbols`, and TeXSmith's own double-quote pattern. Both produce
ordinary text in the document model — there is nothing to reference and nothing
to configure per occurrence — and both are class E: every MkDocs site already
does the same.

= Smart symbols

```md
Copyright (c) 2025, tea (tm), reg (r), c/o Ada: 1/2 a cup, +/- 3, 4 =/= 5, a --> b.
```

renders as

#quote(block: true)[
Copyright #ts-emoji[©] 2025, tea #ts-emoji[™], reg #ts-emoji[®], #ts-script("symbols")[℅ ]Ada: ½ a cup, ± 3, 4 #ts-script("mathematics")[≠ ]5, a #ts-script("symbols")[→ ]b.]

#table(
columns: 3,
align: (left, left, left),
table.header([Group], [Spellings], [Result]),
[Marks], [`(c)` `(tm)` `(r)`], [#ts-emoji[©] #ts-emoji[™] #ts-emoji[®]],
[Care of], [`c/o`], [#ts-script("symbols")[℅]],
[Operators], [`+/-` `=/=`], [± #ts-script("mathematics")[≠]],
[Arrows], [`–>` `<–` `<–>`], [#ts-script("symbols")[→ ← ]#ts-emoji[↔]],
[Fractions], [`1/2` `1/4` `3/4` `1/3` `2/3` `1/5` … `7/8`], [½ ¼ ¾ #ts-script("symbols")[⅓ ⅔ ⅕ ]… #ts-script("symbols")[⅞]],
)

The extension's own boundaries apply: an arrow is not part of a longer run of
dashes (`—>` stays as typed), a fraction is not part of a longer number
(`11/2` and `1/25` stay as typed), and `c/o` must be a whole word.

#ts-callout(kind: "note", title: [What is _not_ substituted])[
- *Ordinal numbers.* `1st` would be a superscript rather than a
character, so it is left alone.
- *`–`, `—` and `...`.* Both paged backends typeset the ASCII
spelling as the dash and the ellipsis on their own; converting them would
gain nothing and lose the round-trip.
- *Anything in code.* No substitution fires inside a code span or a
fenced block.]

= Quotes

A straight-quoted phrase becomes a proper quotation, typeset for the document's
language:

```md
He said "straight quotes", `"not in code"`, and \"not a quote".
```

In #ts-logo("LaTeX") that is `\enquote{straight quotes}`, so French gets guillemets, German
gets low-high quotes and English gets curly quotes — from the root `lang:` key
or the nearest `lang=` attribute, never from the source spelling.

Three rules bound it:

- *Double quotes only.* Single quotes are never paired: an apostrophe is not
a quote.
- *One text run.* A pair whose quotes sit on either side of inline markup
stays literal, because the scan reads a run of text and not the whole
paragraph.
- *`\"` escapes.* A backslash before the opening quote leaves the phrase
alone.

#ts-callout(kind: "tip", title: [Why this matters for print])[]

```
Straight quotes in a PDF are a typographic error, and no template can fix
them after the fact: by the time the text reaches LaTeX, the language is
the only thing that knows which glyphs to use. Writing `"…"` and letting
the substitution run is what puts `\enquote{…}` — and therefore the right
glyphs — in the output.
```

= Language-driven spacing

Punctuation spacing is not a substitution and never a construct in the body:
the narrow no-break space before `;`, `:`, `?` and `!` in French, and the
no-break space between a number and its unit, are applied by the backend from
the document language. `&nbsp;` is accepted as an explicit override.

A passage in another language is a span:

```md
A French sentence with [a quotation in English]{lang=en} inside it.
```

See also Emoji and icons for the other two colon-delimited
substitutions.
