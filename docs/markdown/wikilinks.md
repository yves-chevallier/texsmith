
# Wiki Links

MkDocs and Python-Markdown support the `[[Wiki Link]]` syntax via the `wikilinks`
extension. TeXSmith keeps that behavior so you can link between pages without
remembering exact file paths.

```markdown
[[Getting Started]]
[[Subfolder/Page Title|Custom label]]
```

- The portion before the pipe resolves to a Markdown file (`Getting Started` →
  `getting-started.md`).
- Anything after `|` becomes the rendered link text.
- When building PDFs, TeXSmith turns wiki links into standard hyperlinks, so the
  references remain navigable.
