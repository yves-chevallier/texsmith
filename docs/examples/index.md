# Example

## Scientific Paper

The example `examples/scientific-paper` demonstrates how to create an academic paper using LaTeX formatting, simply from Markdown.

### Build Instructions

To build the scientific paper, run the following command:

```bash
cd examples/scientific-paper
texsmith render cheese.md cheese.bib -tarticle --build
```

![Cheese Article](cheese.png)

## Diagrams

The example `examples/diagrams.md` demonstrates how to embed diagrams in your documentation using Mermaid and Draw.io.

### Build Instructions

To build the documentation with diagrams, run the following command:

```bash
cd examples/diagrams
texsmith render diagrams.md -tarticle --build
```

![Diagram Example](diagrams.png)

## Markdown Feature Showcase

The `examples/markdown/features.md` cheatsheet exercises almost every Markdown extension that TeXSmith supports. Its front matter now demonstrates how a document can inject bespoke LaTeX preamble code (for example to restyle `displayquote`) via `press.override.preamble`.

### Build Instructions

```bash
cd examples/markdown
texsmith render features.md -tarticle --build
```
