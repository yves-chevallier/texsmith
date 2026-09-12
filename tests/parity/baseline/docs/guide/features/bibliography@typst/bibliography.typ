#set document(
title: "Bibliography",
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
#text(size: 1.8em, weight: "bold")[Bibliography]]
#v(1.5em)

TeXSmith reads bibliographic data from #ts-logo("BibTeX") files and from YAML front matter. Use it to keep citations and references tidy in academic writing, technical docs, or any project that wants repeatable citation management.

= Using Bibliography Files

Pass one or more `.bib` files on the command line:

```bash
texsmith docs/chapter.md references.bib
```

You can also add `file1.bib file2.bib` as positional inputs alongside a MkDocs site so every page sees the same pool of references.

= Using the front matter

You can declare bibliography entries directly in the YAML front matter of your Markdown documents:

```yaml
press:
  sources:
    bibliography:
      # Extract citation from DOI
      citation-keyword: https://doi.org/10.1000/xyz123
      # Manual bibliography entry
      AI2027:
        type: misc
        title: AI 2027
        date: 2025-04-03
        url: https://ai-2027.com/ai-2027.pdf
        authors:
          - Daniel Kokotajlo
          - Scott Alexander
          - Thomas Larsen
          - first: Eli
            last: Lifland
          - Romeo Dean
```

A top-level `bibliography:` key is the deprecated spelling; `tmark lint –fix`
moves it under `press.sources`.

The format mirrors #ts-logo("BibTeX"), translated to YAML by `pybtex`.

Two approaches:

+ Provide a DOI link; TeXSmith resolves it into a full #ts-logo("BibTeX") entry.
+ Provide a manual entry with the fields you need.

See the \[academic paper\]\[cheese\] example or the \[book\]\[einstein\] example.

= Citation Syntax

A citation is the `@` sigil against the bibliography registry — the same sigil
that refers to a figure or a section, because the registry decides what the key
means.

```md
---
press:
  sources:
    bibliography:
      WADHWANI20111713: https://doi.org/10.3168/jds.2010-3952
---

# Introduction

Cheese exhibits unique melting properties @WADHWANI20111713.
```

Which renders into:

#figure(
image("snippet-<HASH>.png", width: 70%),
caption: [Demo],
)

`@key` is the in-text (narrative) citation and `@[key, locator]` the
parenthetical one:

```md
As shown by @[WADHWANI20111713, p. 33], and elsewhere
@[see WADHWANI20111713, pp. 33-35; AI2027, ch. 1]. Suppress the author with
@[-WADHWANI20111713], and cite several at once with @[AI2027; WADHWANI20111713].
```

Locators follow Pandoc: a recognised locator word (`p.`, `pp.`, `ch.`, `sec.`,
`§`…) followed by a range, or free suffix text. Pandoc's own `[@key, locator]`
is accepted for import and never emitted.

A DOI can be cited in place through the predeclared `doi` prefix, without a
front-matter entry: `@doi:10.3168/jds.2010-3952`. The same DOI cited twice is
one entry. `@https://doi.org/…` is accepted as sugar and normalised.

Resolution order for any `@key` is: declared counter prefix (`doi` and `gls`
included), then the bibliography. A key present in two registries is a hard
warning, and an unresolved key renders visibly as `[?key]`.

#ts-callout(kind: "note", title: [The footnote spelling is deprecated])[
TeXSmith 0.6 spelled citations `[^key]` and `^[k1,k2]`. Both are still
parsed with a deprecation warning, and while they last the
footnote-versus-citation shadowing rule is preserved: a real footnote with
the same key wins. Once they are retired, `^[…]` becomes an inline
footnote. `tmark lint –fix` rewrites them; see
Migrating to TMark.]

= #ts-logo("BibTeX")

#ts-logo("BibTeX") is an old, loosely specified format with many dialects (`bibtex`, `bibtex8`, `pbibtex`, and more). The most complete parser is #link("https://en.wikipedia.org/wiki/Biber_(LaTeX)")[biber], but it is Perl-based and not embeddable. TeXSmith relies on #link("https://pybtex.org/")[pybtex], which covers the common cases.
