# Render Diagrams Example

This example demonstrates how to include drawio and mermaid diagrams in your Markdown files, which will be automatically converted to images and embedded in the final LaTeX document.

## Prerequisites

To render Mermaid diagrams, you must have either Docker installed or install the Mermaid CLI globally using npm:

```bash
npm install -g @mermaid-js/mermaid-cli
```

To render Draw.io diagrams, you need to have drawio installed or have Docker available. You can install drawio using snap with the following command:

```bash
sudo snap install drawio
```

## Demo

You can run the example with:

```tex
$ uv run texsmith diagrams.md --template article --build
```

TeXSmith automatically resolves built-in template names like `article` even when you
invoke the CLI from nested example directories, so no extra path gymnastics are required.
If you need detailed traces during development, pass `--debug` before the inputs,
e.g. `uv run texsmith --debug diagrams.md …`.
