# Bibliography

The `bibliography` command group provides utilities for inspecting BibTeX files before running a conversion or build. It helps catch parsing issues, duplicate entries, and empty datasets early in your workflow.

```bash
texsmith bibliography [SUBCOMMAND] [OPTIONS] ...
```

Currently, a single subcommand is available: `list`.

## `bibliography list`

```bash
texsmith bibliography list BIBFILE...
```

### Positional Arguments

| Argument | Description |
| -------- | ----------- |
| `BIBFILE...` | One or more BibTeX files to inspect. Each path must exist, be readable, and point to a file (not a directory). |

### Behaviour

- Loads every provided `.bib` file using `pybtex`.
- Prints a formatted table summarising the number of entries per file.
- Emits warnings for files that fail to parse, contain duplicate keys, or are empty.
- Highlights issues detected by TeXSmith’s bibliography loader (e.g. conflicting entries sourced from multiple files).

### Example

```bash
texsmith bibliography list references/articles.bib references/books.bib
```

Use the command to verify bibliographies before your conversion pipeline consumes them. Clean inputs result in clearer LaTeX builds and avoid surprises when `bibtex` or `biber` runs downstream.

If you encounter parsing failures, check for malformed BibTeX entries, unescaped characters, or non-ASCII content that `pybtex` cannot decode.
