# Integration with MkDocs

TeXSmith can be seamlessly integrated with MkDocs, a popular static site generator for project documentation. This allows you to leverage MkDocs' powerful features while utilizing TeXSmith for document generation.

The integration is achieved through the `mkdocs-texsmith` plugin, which processes TeXSmith documents during the MkDocs build process.

## Configuration

To enable TeXSmith in your MkDocs project, you need to add the `mkdocs-texsmith` plugin to your `mkdocs.yml` configuration file:

```yaml
plugins:
  - texsmith
```

You can configure additional options for the TeXSmith plugin as needed:

| Option         | Description                                      | Default          |
|----------------|--------------------------------------------------|------------------|
| `template`     | Template to use for rendering the site           | `book`        |
| `build_dir`    | Directory where TeXSmith outputs are stored      | `site`           |

### Multiple documents

You can either generate one single document from your MkDocs site, or multiple documents from different sections.

```yaml
plugins:
    - texsmith:
      books:
        - template: book
          folder: foolists
          root: "foo"
          base_level: -1
        - template: article
          folder: bariers
          root: "bar"
```

## Serve

During the development with `mkdocs run serve`, TeXSmith plugins can fetch assets from the web (e.g. images, citations) and compile pdf snippets on-the-fly. This allows for a smooth writing experience with instant feedback.

## Build

When you run `mkdocs build`, the TeXSmith plugin processes all TeXSmith documents in your project, generating the corresponding PDFs and integrating them into the final site output. By default the output directory is `press/`.

You can tell TeXSmith to build the PDF during the process with the `build` option in you mkdocs.yml:

```yaml
plugins:
  - texsmith:
      build: true
```
