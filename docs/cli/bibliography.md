# Bibliography

Use the `--list-bibliography` flag to inspect BibTeX files before running a conversion or build. It helps catch parsing issues, duplicate entries, and empty datasets early in your workflow.

```bash
texsmith references/articles.bib references/books.bib --list-bibliography
```

## Inputs

| Argument | Description |
| -------- | ----------- |
| `INPUT...` | One or more documents or `.bib` files. Only `.bib` inputs are inspected when `--list-bibliography` is supplied; Markdown/HTML files are ignored after their front matter is parsed for metadata. |

TeXSmith uses the same path rules as the main conversion workflow: relative or absolute paths are accepted, but each `.bib` file must exist and be readable.

## Behaviour

- Loads every provided `.bib` file using `pybtex`.
- Prints a formatted table summarising the number of entries per file.
- Emits warnings for files that fail to parse, contain duplicate keys, or are empty.
- Highlights issues detected by TeXSmith’s bibliography loader (e.g. conflicting entries sourced from multiple files).
- Exits before rendering anything else, so you can run it as a fast preflight step.

## Example

```bash
texsmith sources/report.md refs/articles.bib refs/books.bib --list-bibliography
```

Use the flag to verify bibliographies before your conversion pipeline consumes them. Clean inputs result in clearer LaTeX builds and avoid surprises when `bibtex` or `biber` runs downstream. If you encounter parsing failures, check for malformed BibTeX entries, unescaped characters, or non-ASCII content that `pybtex` cannot decode.
