# Getting Started

Welcome to TeXSmith! This quick tour gets you from a blank terminal to crisp PDFs. Start by deciding what you need today:

1. Converting standalone Markdown into LaTeX/PDF?
2. Wiring TeXSmith into an existing MkDocs site?
3. Driving it from Python code?

Hop to the section that matches, or ride the whole tour for the full download.

## Prerequisites

TeXSmith expects a few tools already on your machine:

Python 3.10+
: TeXSmith ships as a Python package. Use
  [uv](https://github.com/astral-sh/uv) or `pipx` for isolated installs so the CLI stays tidy.

LaTeX distribution
: Install TeX Live, MiKTeX, or MacTeX so `texsmith render --build`
  can hand off to `latexmk` and friends.

Optional diagram tooling
: Mermaid-to-PDF (`minlag/mermaid-cli`) conversion defaults to Docker.
  Install Docker Desktop (with WSL integration on
  Windows) or register your own converter if Mermaid is part of your workflow.

  Repeat the same idea for Draw.io (`rlespinasse/drawio-desktop-headless`) if they show up in your docs.

Fonts
: TeXSmith prefers Noto for its extensive Unicode coverage. Install
  [Noto Serif](https://www.google.com/get/noto/#serif-lgc) and
  [Noto Sans](https://www.google.com/get/noto/#sans-lgc) for best results.

## Installation

Pick the installer that matches your toolbox:

=== "uv"

    ```bash
    uv tool install texsmith
    ```

=== "pip"

    ```bash
    pip install texsmith
    ```

=== "pipx"

    ```bash
    pipx install texsmith
    ```

## Convert a Markdown file to LaTeX

By default TeXSmith converts any Markdown file to LaTeX. It can also parse an HTML file:

=== "Here document"

    ```bash
    $ cat << EOF | texsmith render
    # Title
    Some **bold** text.
    EOF
    \chapter{Title}\label{title}

    Some \textbf{bold} text.
    ```

=== "From file"

    ```bash
    $ echo "# Title\nSome **bold** text." > sample.md
    $ texsmith render sample.md --output build/
    \chapter{Title}\label{title}

    Some \textbf{bold} text.
    ```

=== "HTML"

    ```bash
    $ echo "<h1>Title</h1><p>Some <strong>bold</strong> text.</p>" > sample.html
    $ texsmith render sample.html
    \chapter{Title}
    Some \textbf{bold} text.
    ```

## Convert a Markdown file

Imagine you want to write an article about boobies. Create a sample Markdown file that you name `booby.md` or reuse our example:

```markdown
--8<--- "examples/booby/booby.md"
```

Notice the front matter at the top that specify information about the document
like title, author, date, and template to use.

Then let TeXSmith crunch it:

```bash
texsmith render booby.md --output build/ -apaper=a5 --build
```

Enjoy a fresh PDF at `build/booby.pdf`:

[![Booby](../assets/examples/booby.png){width=60%}](../assets/examples/booby.pdf)

Peek inside `build/` and you will find `booby.tex`. Be free to change the  `--template` when you want a full LaTeX project or a polished PDF:

```bash
texsmith render booby.md --template article --output-dir build
```

## Use the Python API

TeXSmith is also a Python library. Create a file named `demo.py` with the following content:

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

Run the snippet with `uv run python demo.py`. The API mirrors the CLI, so
drop into `ConversionService` or `TemplateSession` whenever you need more
control over slot assignments, diagnostic emitters, or template metadata.

## Convert a MkDocs site

Point TeXSmith at a MkDocs site once `mkdocs build` renders clean HTML:

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

    - The default selector (`article.md-content__inner`) already matches MkDocs Material content; skip `--selector` unless you heavily customise templates.
    - When your site spans multiple documents, repeat the command per page and stitch them with template slots (for example, `--slot mainmatter:build/site/manual/index.html`).
    - For live previews, point TeXSmith at the temporary site directory that `mkdocs serve` prints on startup.

    Once the LaTeX bundle looks good, add `--build` to invoke `latexmk` or wire everything into CI so MkDocs HTML → TeXSmith PDF happens on every run.


## How does TeXSmith work?

![Workflow diagram of TeXSmith](../assets/workflow.drawio)
