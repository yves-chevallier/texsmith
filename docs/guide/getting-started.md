# Getting Started

Welcome to TeXSmith! This guide walks you through the initial setup. I may first ask you a question:

1. Do you need TeXSmith for converting sole Markdown files into LaTeX/PDF documents?
2. Are you planning on integrating TeXSmith with an existing MkDocs site?
3. Will you be using TeXSmith programmatically via the Python API?

Jump to the relevant section accordingly, or follow the entire guide for a comprehensive overview.

## Prerequisites

TeXSmith requires the following components:

Python 3.10+
: TeXSmith ships as a Python package. We recommend
  [uv](https://github.com/astral-sh/uv) or `pipx` for isolated installs.

LaTeX distribution
: Install TeX Live, MiKTeX, or MacTeX so `texsmith render --build`
  can call `latexmk` and friends.

Optional diagram tooling
: Mermaid-to-PDF conversion defaults to Docker
  (`minlag/mermaid-cli`). Install Docker Desktop (with WSL integration on
  Windows) or register your own converter if you rely on Mermaid diagrams.

  Do the same for Draw.io diagrams if you plan to embed them in your documents.

## Installation

You have two main options to install TeXSmith:

=== "uv"

    ```bash
    uv tool install texsmith
    ```

=== "pip / pipx"

    ```bash
    pip install texsmith
    # or
    pipx install texsmith # Respect PEP 660 isolation
    ```

## Convert a Markdown file

Create a sample Markdown file `booby.md` or use the snippet below:

```markdown
--8<--- "examples/booby/booby.md
```

Then invoke TeXSmith from the command line:

```bash
texsmith render booby.md --output build/ -tarticle -paper=a5 --build
```

You will get a pdf file `build/booby.pdf` ready for printing:

[![Booby](../assets/examples/booby.png){width=60%}](../assets/examples/booby.pdf)

You should see `intro.tex` in the `build/` directory. Add the `--template`
option (and a template package) to emit complete LaTeX projects or PDFs:

```bash
texsmith render intro.md --template article --output-dir build/pdf --build
```

## Use the Python API

```python
from pathlib import Path

from texsmith import Document, convert_documents

bundle = convert_documents(
    [Document.from_markdown(Path("intro.md"))],
    output_dir=Path("build"),
)

print("Fragments:", [fragment.stem for fragment in bundle.fragments])
print("Preview:", bundle.combined_output()[:120])
```

Run this snippet with `uv run python demo.py`. The API mirrors the CLI, so
switch to `ConversionService` or `TemplateSession` whenever you need more
control over slot assignments, diagnostic emitters, or template metadata.

## Convert a MkDocs site

Use TeXSmith once your MkDocs project already renders clean HTML:

```bash
# Build your MkDocs site into a disposable directory
mkdocs build

# Convert one page into LaTeX/PDF-ready assets
texsmith render build/site/guides/overview/index.html \
  --template article \
  --output-dir build/press \
  --bibliography docs/references.bib
```

!!! tip

    - The default selector (`article.md-content__inner`) already targets MkDocs Material content; omit `--selector` unless you heavily customise templates.
    - When your site spans multiple documents, repeat the command per page and combine them with template slots (for example, `--slot mainmatter:build/site/manual/index.html`).
    - For live previews, hook TeXSmith to `mkdocs serve` by pointing at the temporary site directory MkDocs prints on startup.

    Once the LaTeX bundle looks good, add `--build` to invoke `latexmk` or wire the commands into CI so MkDocs HTML → TeXSmith PDF generation happens automatically.


## How does TeXSmith work?

![Workflow diagram of TeXSmith](../assets/workflow.drawio)
