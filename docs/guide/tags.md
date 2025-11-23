[](){ #index-tags }
# Index Generation

In static site generators such as MkDocs, every build emits a `search_index.json`
file consumed by Lunr.js or Wasabi directly in the browser. It lists every word
encountered in the documentation along with its locations, enabling instant
client-side search. That automation works wonderfully for HTML, but printed
documents require a static index compiled ahead of time.

Traditional LaTeX editing relies on `\index{term}` commands sprinkled throughout
the source. After compilation you run `makeindex` or `xindy`, which produces the
final index file included near the end of the document. TeXSmith mirrors that
workflow: it turns Markdown annotations into LaTeX `\index{...}` calls and
triggers `makeindex`/`xindy` while building the PDF.

The LaTeX form still looks familiar:

```latex
\index{term!subterm}
\index{another term}
\index{\textbf{important term}}
\index{\emph{emphasized term}}
```

Thus, index entries can:

- be nested up to 3 levels,
- be rendered in bold, italic or both,
- appear multiple times in the document, with all page numbers listed.

To mimic this behavior in Markdown, the `texsmith.index` extension provides the
hashtag syntax:

```markdown
#[a] One level index entry in the default index
#[a][b][c] Three-level entry in the default index
{index:registry}[Foo][Bar] Entry nested twice under the `registry` index
#[*a*] Formatted index entry in default index
#[**a**] Bold formatted index entry in default index
#[***a***] Bold italic formatted index entry in default index
#[a] #[b] Multiple index entries in one place
```

## Emphasis and Formatting

Printed indexes often differentiate how important an entry is within a section:

- Normal text: the term is discussed in that section (default).
- **Bold**: the term is the main topic of that section.
- *Italic*: the term is mentioned but not deeply discussed.
- ***Bold italic***: the term is the main topic and also referenced elsewhere in the same section.

Because the hashtag syntax accepts Markdown formatting, just wrap the indexed term
in the appropriate markers (e.g. `#[**topic**]`).

## Nested Entries

Consider a cooking book where you want to index the recipe for "Chocolate Cake". You might want to add
an index entry for "Cake" with a sub-entry for "Chocolate" and also in "Chocolate Cake":

```markdown
## Chocolate Cake

#[cake][**chocolate**] #[chocolate cake]
```

LaTeX only supports up to 3 levels of nesting:

```markdown
#[cake]
#[cake][**chocolate**]
#[dessert][cake][chocolate]
```

## Tags

In MkDocs, search powered by Lunr.js automatically adds tags on headings to improve searchability.
From an HTML perspective the extension emits invisible spans such as
`<span class="ts-hashtag" data-tag="term" data-style="b">`. The LaTeX renderer
converts them into the proper `\index{...}` call while the MkDocs plugin collects
the same metadata to enrich Lunr’s search index. This keeps the PDF index and the
interactive site search in sync even though they are generated through different pipelines.
