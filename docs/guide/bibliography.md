# Bibliography

TeXSmith is capable of processing bibliographic data stored in BibTeX files and references into the Markdown front matter. This allows you to manage citations and bibliographies in your MkDocs projects seamlessly.

## Using Bibliography Files

When invoking `texsmith`, you can specify one or more BibTeX files:

```bash
texsmith docs/chapter.md references.bib
```

## Using the front matter

You can also declare bibliography entries directly in the YAML front matter of your Markdown documents:

```yaml
bibliography:
  # Extract citation from DOI
  citation-keyword: https://doi.org/10.1000/xyz123
  # Manual bibliography entry
  AI2027:
    title: AI 2027
    type: misc
    date: 2025-04-03
    url: https://ai-2027.com/ai-2027.pdf
    authors:
      - Daniel Kokotajlo
      - Scott Alexander
      - Thomas Larsen
      - Eli Lifland
      - Romeo Dean  
```

## Citation Syntax

Citations in your Markdown documents should follow the footnote-style syntax:

```yaml
---
bibliography:
  WADHWANI20111713: https://doi.org/10.3168/jds.2010-3952
---
# Introduction

Cheese exhibits unique melting properties [^WADHWANI20111713].
```

If the citation key is not found in the provided bibliography files, then the standard footnote will be rendered instead.
If a footnote exists with the same key, then it will take precedence over the bibliography entry.
