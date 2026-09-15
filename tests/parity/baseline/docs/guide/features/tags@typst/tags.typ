#set document(
title: "Index Generation",
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
#text(size: 1.8em, weight: "bold")[Index Generation]]
#v(1.5em)

#ts-callout-style.update("fancy")

#metadata(none) <index-tags>

In static site generators such as MkDocs, every build emits a `search_index.json`
file consumed by Lunr.js or Wasabi directly in the browser. It lists every word
encountered in the documentation along with its locations, enabling instant
client-side search. That automation works wonderfully for HTML, but printed
documents require a static index compiled ahead of time.

Traditional #ts-logo("LaTeX") editing relies on `\index{term}` commands sprinkled throughout
the source. After compilation you run `makeindex` or `xindy`, which produces the
final index file included near the end of the document. TeXSmith mirrors that
workflow: it turns Markdown annotations into #ts-logo("LaTeX") `\index{...}` calls and
triggers `makeindex`/`xindy` while building the PDF.

The #ts-logo("LaTeX") form still looks familiar:

```latex
\index{term!subterm}
\index{another term}
\index{\textbf{important term}}
\index{\emph{emphasized term}}
```

Thus, index entries can:

- be nested up to 3 levels,
- be rendered in bold, italic, or both,
- appear multiple times in the document, with all page numbers listed.

TMark spells an index entry with the `index` role, and `#[…]` is its shorthand —
`#` defines, and the term is _content_, hence the brackets. The two spellings
are one node.

```md
{index}[endianness]                     one level, default registry
#[endianness]                           the same thing, shorthand

#[byte order][endianness]               nested (three levels at most)

{index main=true}[endianness]           main topic: a bold page number
#[**endianness**]                       the same thing, shorthand

#[*endianness*]                         emphasis is content markup

{index registry=physics}[Foo][Bar]      nested twice under a named registry

#[cake] #[chocolate]                    several entries in one place
```

A registry other than the default is named by `registry=`; it is created on
first use and each produces its own index at the position the template chooses.

#ts-callout(kind: "note", title: [`{index:reg}` and the `{b}` / `{i}` suffixes are deprecated])[
The 0.6 spellings `{index:registry}[…]` and `{index}[…]{b}` / `{i}` are
still parsed with a deprecation warning. `tmark lint –fix` rewrites them to
`{index registry=…}[…]` and `{index main=true}[…]`; italics become content
markup. See Migrating to TMark.]

= Emphasis and Formatting

Printed indexes often differentiate how important an entry is within a section:

- Normal text: the term is discussed in that section (default).
- *Bold*: the term is the main topic of that section.
- _Italic_: the term is mentioned but not deeply discussed.
- _*Bold italic*_: the term is the main topic and also referenced elsewhere in the same section.

Emphasis inside the term is content markup, so wrap the indexed term in the
appropriate markers (`#[*topic*]`); "main topic" is the `main=true` attribute,
for which `#[**topic**]` is the shorthand.

= Nested Entries

Consider a cooking book where you want to index the recipe for "Chocolate Cake". You might want to add
an index entry for "Cake" with a sub-entry for "Chocolate" and also in "Chocolate Cake":

```md
## Chocolate Cake

#[cake][**chocolate**] #[chocolate cake]
```

#ts-logo("LaTeX") only supports up to 3 levels of nesting:

```md
#[cake]

#[cake][**chocolate**]

#[dessert][cake][chocolate]
```

= Tags

In MkDocs, search powered by Lunr.js automatically adds tags on headings to
improve searchability. An index entry is a *zero-width* node: the whitespace
on both sides collapses to one space and disappears before punctuation, so it
never shows in the flow. The #ts-logo("LaTeX") writer emits `\tsindex[registry=r,
main]{sort@formatted!sub}` from the `ts-index` fragment, and the MkDocs plugin
collects the same entries to enrich Lunr's search index. This keeps the PDF
index and the interactive site search in sync even though they are generated
through different pipelines.
