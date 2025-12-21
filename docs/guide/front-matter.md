# YAML Front Matter

Markdown supports a special section at the top of the document called "front matter" that allows you to specify metadata about the document.
MkDocs or other static site generators use this section to configure page-specific settings.

TeXSmith extends this functionality to include additional options that can influence how your Markdown files are processed and rendered into LaTeX/PDF.

## Press

You can use the `press` option in the front matter to specify information related to TeX production:

```yaml
press:
  title: "My Document Title"
  subtitle: "An In-depth Exploration"
  template: article
  authors:
    - name: "Alice Smith"
      affiliation: "University of Examples"
  slots:
    abstract: Abstract
```

Template-specific attributes can be referenced in the front matter as well. See the [Template Guide](templates/index.md) for more details.

## Bibliography

Bibliography entries can also be specified in the front matter. See the [Bibliography Guide](features/bibliography.md) for more details.

```yaml
bibliography:
  AB2020: doi:10.1000/xyz123
  CD2019:
    type: book
    author: "John Doe"
    title: "Example Book"
    year: "2019"
```
