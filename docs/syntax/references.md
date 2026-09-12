# References

TMark has **one sigil for referring**: `@`. Whatever the target — a section, a
figure, a table, an equation, a custom counter, a glossary term, a bibliography
entry, another document — you write `@key`, and the registry the key belongs to
decides what the reference renders as.

The mnemonic is short: **`#` defines, `@` refers.**

We define several types of references that can be used throughout the documentation:

Internal References
: Links that point to other sections within the same document or to other documents within the same project.

External References
: Links that point to resources outside of the current project, such as websites or external documents.

Bibliographic References
: Citations that refer to external publications, articles, or books. They are formatted using a citation style (APA, MLA, …) and gather into a bibliography.

Footnotes
: Additional information parked at the bottom of the page, marked with a superscript number.

Equations, Tables, Figures, Listings
: Numbered floats with an anchor, referenced by their key.

Tags/Index
: Keywords associated with a section or topic, gathered into a printed index.

## The two forms of `@`

```md
@sec:intro                   bare, in-text: "section 2"
@Sec:intro                   capitalised prefix, for the start of a sentence
@[fig:boot; fig:crash]       grouped → "figures 1 and 2"
@[tbl:stock, column 3]       with a suffix → "table 4, column 3"
[](#sec:intro)               empty-link form, for pure-Markdown toolchains
[](other.md)                 section number of another document's main heading
```

The brackets follow the sigil and are **optional**: a bare `@key` takes one word
of `[A-Za-z0-9_:.-]` and ends on an alphanumeric, so trailing sentence
punctuation stays out (`…voir @sec:intro.` references `sec:intro`). The
bracketed form is required as soon as the reference contains a space — a
locator, a suffix, or several keys separated by `;`.

E-mail addresses, URLs and `@` inside a word never match; write `\@` to force a
literal `@` where the sigil would otherwise fire. An unresolved reference
renders visibly as `[?key]` and warns.

## Internal References

You can reference another section in the same document or cross-link to other files in the project.

Linking to another file? TeXSmith targets the destination’s main heading and drops a proper hyperlink—handy for navigation-friendly PDFs without any manual tinkering.

```md
See the [Code Examples](code.md) for more details.
```

Skip the link text and TeXSmith injects the section number for the print build automatically.

```md
See the section [](code.md) for more details.
```

```md
## Section Title {#sec:section-title}

Placeholder text that other sections can reference.

## Other Section

Check @sec:section-title for more details.
```

A heading with no `{#id}` still has an *implicit* id — GitHub's slug of its
plain text — so `[](#other-section)` resolves. Because that id changes whenever
the title is edited, referring to one raises the `ref-implicit-id` hint: give
the heading an explicit `{#sec:…}`. See [Headings](headings.md) for the slug
rule and for `.unnumbered` / `.unlisted`.

### Custom counters

Document-specific series (findings, requirements, bugs) declared under
`press.declare.counters` in the front matter reuse the very same `@prefix:key`
form, resolving to their formatted number instead of a section number. See
[Custom counters](counters.md).

### Cross-document references

`@alias:key` resolves against another document's published inventory, declared
under `press.sources.crossrefs` in the front matter. See
[Cross-document references](crossrefs.md).

### Autorefs

When the `mkdocs-autorefs` extension is enabled, you can use the `[text][label]` syntax to generate automatic references to headings.

## External References

Reference external resources (HTTP/HTTPS) with vanilla Markdown link syntax:

```md
For more information, visit the [TeXSmith Website](https://texsmith.org).
You can also check our repository at https://github.com/yves-chevallier/texsmith.
```

Printed output uses the usual LaTeX link commands:

```latex
For more information, visit the \href{https://texsmith.org}{TeXSmith Website}.
You can also check our repository at \url{https://github.com/yves-chevallier/texsmith}.
```

## Bibliographic References

A citation is the same sigil against the bibliography registry. `@key` is the
in-text (narrative) citation, `@[key, locator]` the parenthetical one, and
`@[-key]` suppresses the author.

```md
---
press:
  sources:
    bibliography:
      ein05: https://doi.org/10.1002/andp.19053221004
---

Einstein's theory of relativity revolutionized physics @ein05.
As shown by @[ein05, p. 33], and elsewhere @[see ein05, pp. 33-35].
```

A DOI can be cited in place through the predeclared `doi` prefix, without a
front-matter entry: `@doi:10.1002/andp.19053221004`.

!!! note "The footnote spelling of a citation is deprecated"
    TeXSmith 0.6 spelled citations `[^key]` and `^[k1,k2]`, borrowing the
    footnote syntax. Both are still accepted with a deprecation warning; once
    they are retired, `^[…]` becomes an inline footnote (Pandoc's meaning).
    `tmark lint --fix` rewrites them to `@key` and `@[k1; k2]`. Real footnotes
    (`[^1]` with a definition) are untouched.

See [Bibliography management](../guide/features/bibliography.md) for the
sources, and [Migrating to TMark](../guide/migration.md) for the rewrite.

## Footnotes

Use footnotes to park side comments without cluttering the main text. Markdown marks them with superscript numbers; the rendered document moves the details to the bottom of the page or section.

```md
This is a sample sentence with a footnote.[^1]

[^1]: This is the footnote text that provides additional information.
```

Footnotes are limited to one line in print—keep them tight.

## Equations

Display math takes an anchor after the closing delimiter, Quarto-style, and is
referenced like any other numbered object:

```md
$$
E = mc^2
$$ {#eq:einstein}

As shown in @eq:einstein, energy is equal to mass times the speed of light
squared.
```

The LaTeX-flavoured compatibility forms keep working: `\begin{equation}
\label{eq:x} … \end{equation}` inside `$$`, referenced with `$\eqref{eq:x}$`.

## Figures

Give a figure a caption line with an id and refer to it with `@`:

```md
![Sample Figure](image-url.jpg)

Figure: This is the caption for the figure. {#fig:sample}

As shown in @fig:sample, the data illustrates…
```

The id is emitted verbatim as the LaTeX `\label`. Both web and print outputs
number figures automatically, though the actual numbers may differ because each
layout floats content differently.

## Tables

Tables take a caption line too; the canonical position is after the table.

```md
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |

Table: A sample table for cross-references. {#tbl:sample}

Check @tbl:sample for more details.
```

## Code Block References

A `Listing:` caption line promotes a fenced code block to a numbered,
referenceable listing:

````md
```python title="bubble_sort.py"
def bubble_sort(items): ...
```

Listing: Bubble sort, naive version. {#lst:bubble}

@lst:bubble is quadratic in the worst case.
````

## Tags and Index Entries

Add index entries to associate keywords with specific topics. Defining is the
other sigil:

```md
This section covers advanced sorting algorithms. #[algorithm]
```

The canonical role form is `{index}[algorithm]`; `#[…]` is its shorthand, and
both produce the same node. See [Index / Tags](../guide/features/tags.md) for
nesting, main entries and named registries.

## Naming Conventions

Before hypertext, references revolved around numbers: pages, figures, tables, equations.

```text
1. Section

  Some Text

  Table 7: An example table
         +-------+
         | Table |
         +-------+

         +--------+
         | Figure |
         +--------+
  Figure 42: An example figure

2. Another Section

  See Table 7 for more details. The Figure 42 illustrates the concept.
  Everything is explained in Section 1.
```

The counter registry carries the label word per language, so the same `@`
reference reads correctly in every locale.

### French

In French, the reference type stays lowercase unless it begins the sentence.

> Voir le tableau 7 pour plus de détails. La figure 42 illustre le concept.
> Le tout est expliqué à la section 1.

### English

In English we capitalize the reference type and skip the article (“Table 7,” not “the Table 7”).

> See Table 7 for more details. Figure 42 illustrates the concept.
> Everything is explained in Section 1.

### German

German capitalizes the reference type too.

> Siehe Tabelle 7 für weitere Details. Abbildung 42 veranschaulicht das Konzept.
> Alles wird in Abschnitt 1 erklärt.
