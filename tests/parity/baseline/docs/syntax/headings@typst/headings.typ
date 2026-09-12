#set document(
title: "Headings",
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
#text(size: 1.8em, weight: "bold")[Headings]]
#v(1.5em)

`#` to `######`, six levels, *never numbered by hand*. Numbering and the
mapping to #ts-logo("LaTeX") sectioning come from `press.base_level` and the template.
Attributes go at the end of the line.

```md
# Firmware review

## Boot sequence {#sec:boot}
```

Headings are _relative_: TeXSmith realigns a multi-file hierarchy on its own —
a per-fragment offset from the shallowest heading, plus the template slot base,
plus `press.base_level` — and promotes the first heading to the document title
unless `title:` is declared. That is processing, not syntax.

= Implicit ids

A heading without `{#id}` still has an id, so the link forms resolve to it as
they do on GitHub and on every Python-Markdown site:

```md
## Boot sequence

See [](#boot-sequence) and [the boot sequence](#boot-sequence).
```

The rule is GitHub's: take the plain text of the heading (inline markup and
code reduced to their text, zero-width nodes and the attribute list removed),
NFC-normalise it, lower-case it, drop every character that is not a letter, a
digit, a combining mark, a space, `-` or `_`, and turn runs of spaces into one
`-`. A duplicate gets `-1`, `-2`, … in document order. Accents and non-Latin
scripts survive, as they do on GitHub and MkDocs Material.

The implicit id is a label like any other — `@boot-sequence` renders
"section 2" — but it is derived at resolution, never stored and never printed,
so the round-trip is untouched. An explicit `{#id}` replaces it: a heading has
one id.

#ts-callout(kind: "warning", title: [A reference to an implicit id is hinted])[
Editing the title changes the id and silently breaks every reference to it,
so referring to one raises the hint `ref-implicit-id`, which suggests you
write `{#id}`. A site whose slugifier is not GitHub's (Python-Markdown's
default `toc` drops accents) needs an explicit id anyway — which is the
recommendation in any case.]

= Unnumbered and unlisted

Two classes, both Pandoc's, each applying to its own heading only:

```md
# Preface {.unnumbered}

## Colophon {.unlisted}
```

/ `.unnumbered`: Takes the heading out of the numbering sequence — `\section*`,
`numbering: none`, `class="unnumbered"`.
/ `.unlisted`: Does that _and_ keeps the heading out of the table of contents.

The document-level default is `press.numbered`, true by default, which either
class overrides one heading at a time.

#ts-callout(kind: "note", title: [`{-}` is not an attribute list])[
Pandoc's shorthand for an unnumbered heading relies on bare-word
attributes, which TMark does not have (see Attributes), so
`{-}` stays literal text. The Pandoc importer rewrites it.]

= Anchors and references

A heading's `{#id}` is an anchor like any other, and the *host
decides the counter*: a heading is a section, so `@sec:boot` renders
"section 2". A prefix is required only where no host tells the kind — or where
you want the heading numbered in a custom series instead of its
own:

```md
---
press:
  declare:
    counters:
      fw: {name: Finding, format: "FW-{n:02d}"}
---

## Boot loop {#fw:boot-loop}

The watchdog issue (@fw:boot-loop) is fixed in 1.4.2.
```

See References for the reference forms.
