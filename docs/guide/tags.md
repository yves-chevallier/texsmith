[](){ #index }
# Index Generation

In static site generators like MkDocs, a search based index can be generated
to help users quickly find content through full-text search. However in printed documents,
an index can be useful to provide a list of important terms and their locations in the text.

Index in LaTeX documents is typically created using the `imakeidx` package, which allows you to
define index entries in your source files and generate an index section which refers to the pages where
those terms appear. The LaTeX form is typically:

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

To mimic this behavior in TeXSmith, the `index` extension provides the `@{}` shortcode:

```markdown
Albert Einstein @{Albert Einstein} is known for the theory of relativity
theory @{theory}{*relativity*}.
```

## Emphasis and Formatting

Traditionally index entries can be emphasized which have special meaning in litterature.

- Bold entries are used for main topics or important terms.
- Italic entries are used for terms mentioned in passing or less significant terms.
- Bold + Italic entries are used for terms that are both important and mentioned in passing.

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
TeXSmith extension `texsmith.index` adds both index entries and tags when the `#[]` syntax is used.