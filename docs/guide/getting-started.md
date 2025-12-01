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

Yes folks, that's right. Only Python is required. No need to wrestle with TeX
distributions... yet.

## Optional prerequisites

LaTeX distribution (Optional)
: Install TeX Live, MiKTeX, or MacTeX so `texsmith --build`
  can hand off to Tectonic (default) or `latexmk` when you opt into `--engine lualatex` / `--engine xelatex`.

Diagram tooling (Optional)
: Mermaid-to-PDF (`minlag/mermaid-cli`) conversion defaults to Docker.
  Install Docker Desktop (with WSL integration on
  Windows) or register your own converter if Mermaid is part of your workflow.

  Draw.io and Mermaid diagrams try a Playwright-based exporter first (cached under `~/.cache/texsmith/playwright`),
  then the local CLI, then Docker (`rlespinasse/drawio-desktop-headless` / `minlag/mermaid-cli`). Use
  `--diagrams-backend=playwright|local|docker` to force a specific backend.

Fonts
: TeXSmith uses Noto for fallback due to its extensive Unicode coverage. You may also want to install additional fonts for specific scripts or to match your document design.

## Installation

Pick the installer that matches your toolbox:

=== "pip"

    ```bash
    pip install texsmith
    ```

=== "pipx"

    ```bash
    pipx install texsmith
    ```

=== "uv"

    ```bash
    uv tool install texsmith
    ```

## Convert a Markdown file to LaTeX

By default TeXSmith converts any Markdown file to LaTeX. It can also parse an HTML file:

=== "Here document"

    ```text
    $ cat << EOF | texsmith
    # Title
    Some **bold** text.
    EOF
    \chapter{Title}\label{title}

    Some \textbf{bold} text.
    ```

=== "From file"

    ```text
    $ echo "# Title\nSome **bold** text." > sample.md
    $ texsmith sample.md --output build/
    \chapter{Title}\label{title}

    Some \textbf{bold} text.
    ```

=== "HTML"

    ```text
    $ echo "<h1>Title</h1><p>Some <strong>bold</strong> text.</p>" > sample.html
    $ texsmith sample.html
    \chapter{Title}
    Some \textbf{bold} text.
    ```

## Generate a PDF

Imagine you desperatly want to write an article about [boobies](https://en.wikipedia.org/wiki/Booby). Create a sample Markdown file that you name `booby.md` or reuse our example:

```markdown
--8<--- "examples/booby/booby.md"
```

Notice the front matter at the top that specify information about the document
like title, author, date, and template to use.

Then let TeXSmith crunch it:

```bash
texsmith booby.md --output build/ -apaper=a5 --build
```

With Tectonic as the default engine, all fonts, packages and dependencies are automatically resolved. Even Tectonic itself is downloaded on demand if missing. You truly need nothing else installed to get started.

Enjoy a fresh PDF at `build/booby.pdf`:

```md {.snippet data-caption="Demo" data-width="60%" data-cwd="../../examples/booby"}
--8<--- "examples/booby/booby.md"
```

Peek inside `build/` and you will find `booby.tex`. Be free to change the  `--template` when you want a full LaTeX project or a polished PDF:

```bash
texsmith booby.md --template article --output-dir build
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

Run the snippet with `python demo.py`. The API mirrors the CLI, so
drop into `ConversionService` or `TemplateSession` whenever you need more
control over slot assignments, diagnostic emitters, or template metadata.

## Convert a MkDocs site

Point TeXSmith at a MkDocs site once `mkdocs build` renders clean HTML:

```bash
# Build your MkDocs site into a disposable directory
mkdocs build

# Convert one page into LaTeX/PDF-ready assets
texsmith build/site/guides/overview/index.html \
  --template article \
  --output-dir build/press \
  --bibliography docs/references.bib
```

!!! tip

    - The default selector (`article.md-content\_\_inner`) already matches MkDocs Material content; skip `--selector` unless you heavily customise templates.
    - When your site spans multiple documents, repeat the command per page and stitch them with template slots (for example, `--slot mainmatter:build/site/manual/index.html`).
    - For live previews, point TeXSmith at the temporary site directory that `mkdocs serve` prints on startup.

    Once the LaTeX bundle looks good, add `--build` to invoke your chosen engine or wire everything into CI so MkDocs HTML → TeXSmith PDF happens on every run.

## How does TeXSmith work?

TeXSmith ingests Markdown, HTML or even YAML files, then processes them through a series of steps to produce LaTeX or PDF output.

A template can be associated to allow custom layouts and therefore build into a PDF. Each templates defines slots that get filled with content from the source documents.

A template manifest also describes compatible **fragments** that provide additional content or styling to the final document (e.g. bibliography, glossary, index, fonts, page geometry, typesetting options...).

![Workflow diagram of TeXSmith](../assets/workflow.drawio)

TeXSmith embeds engines to convert rich diagrams (Mermaid, Draw.io) into PDFs that get included in the LaTeX output. It also supports different LaTeX engines (Tectonic, LuaLaTeX, XeLaTeX) to suit your typesetting needs.
