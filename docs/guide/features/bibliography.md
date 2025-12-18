# Bibliography

TeXSmith reads bibliographic data from BibTeX files and from YAML front matter. Use it to keep citations and references tidy in academic writing, technical docs, or any project that wants repeatable citation management.

## Using Bibliography Files

Pass one or more `.bib` files on the command line:

```bash
texsmith docs/chapter.md references.bib
```

You can also add `file1.bib file2.bib` as positional inputs alongside a MkDocs site so every page sees the same pool of references.

## Using the front matter

You can declare bibliography entries directly in the YAML front matter of your Markdown documents:

```yaml
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

The format mirrors BibTeX, translated to YAML by `pybtex`.

Two approaches:

1. Provide a DOI link; TeXSmith resolves it into a full BibTeX entry.
2. Provide a manual entry with the fields you need.

See the [academic paper][cheese] example or the [book][einstein] example.

## Citation Syntax

Citations use the footnote-style syntax:

```yaml
---
bibliography:
  WADHWANI20111713: https://doi.org/10.3168/jds.2010-3952
---
# Introduction

Cheese exhibits unique melting properties [^WADHWANI20111713].
```

Which renders into:

```md {.snippet caption="Demo"}
---
bibliography:
  WADHWANI20111713: https://doi.org/10.3168/jds.2010-3952
---
# Introduction

Cheese exhibits unique melting properties [^WADHWANI20111713].
```

If a citation key is missing from your bibliography, TeXSmith leaves it as a regular footnote. If a footnote exists with the same key, the footnote wins over the bibliography entry.

## BibTeX

BibTeX is an old, loosely specified format with many dialects (`bibtex`, `bibtex8`, `pbibtex`, and more). The most complete parser is [biber](https://en.wikipedia.org/wiki/Biber_(LaTeX)), but it is Perl-based and not embeddable. TeXSmith relies on [pybtex](https://pybtex.org/), which covers the common cases.
