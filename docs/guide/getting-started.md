# Getting Started

Welcome to TeXSmith—the fast lane from an empty terminal to a polished PDF. Pick your mission:

1. Turn Markdown or HTML into LaTeX/PDF.
2. Drop TeXSmith into an existing MkDocs site.
3. Drive it from Python.

Hop to the section you need or read straight through for the big picture.

## Prerequisites

TeXSmith only asks for one base tool:

Python 3.10+
: TeXSmith ships as a Python package. Install with
  [uv](https://github.com/astral-sh/uv) or `pipx` to keep the CLI isolated from your system Python.

That is it. No TeX distribution is required to get started—Tectonic will self-bootstrap when needed.

## Optional prerequisites

LaTeX distribution
: Install TeX Live, MiKTeX, or MacTeX if you want TeXSmith to hand off builds to `latexmk` (`--engine lualatex` / `--engine xelatex`). The default route uses Tectonic, which auto-installs itself and required packages.

Diagram tooling
: Mermaid-to-PDF (`minlag/mermaid-cli`) conversion falls back to Docker. Install Docker Desktop (with WSL integration on Windows) or register your own converter if Mermaid diagrams are common in your docs.

  Draw.io and Mermaid diagrams try a Playwright exporter first (cached under `~/.cache/texsmith/playwright`), then the local CLI, then Docker (`rlespinasse/drawio-desktop-headless` / `minlag/mermaid-cli`). Use `--diagrams-backend=playwright|local|docker` to pin a specific backend.

Fonts
: TeXSmith ships with Noto fallback for wide Unicode coverage. Add your own fonts if you want a specific script or branded look.

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

By default TeXSmith writes LaTeX to stdout. Pipe it or direct it into a folder. HTML works too:

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

Want the full PDF? Start with our playful [booby](https://en.wikipedia.org/wiki/Booby) example or create your own `booby.md`:

```markdown
--8<--- "examples/booby/booby.md"
```

Notice the front matter up top: it carries the title, author, date, and template to use.

Then let TeXSmith crunch it:

```bash
texsmith booby.md --output build/ -apaper=a5 --build
```

With Tectonic as the default engine, fonts, packages, and dependencies resolve themselves on demand (including Tectonic if it is missing). Nothing else to install.

Enjoy a fresh PDF at `build/booby.pdf`:

```md {.snippet data-caption="Demo" data-width="60%" data-cwd="../../examples/booby"}
--8<--- "examples/booby/booby.md"
```

Peek inside `build/` to find `booby.tex`. Swap `--template` when you want a different LaTeX project layout or polish level:

```bash
texsmith booby.md --template article --output-dir build
```

## Use the Python API

TeXSmith also ships as a Python library. Create `demo.py`:

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

Run the snippet with `python demo.py`. The API mirrors the CLI; reach for `ConversionService` or `TemplateSession` when you need fine-grained control over slot assignments, diagnostics, or template metadata.

## Convert a MkDocs site

Point TeXSmith at a MkDocs site after `mkdocs build` renders clean HTML:

```bash
# Build your MkDocs site into a disposable directory
mkdocs build

# Convert one page into LaTeX/PDF-ready assets
texsmith build/site/guides/overview/index.html \
  --template article \
  --output-dir build/press \
  docs/references.bib
```

!!! tip

    - The default selector (`article.md-content\_\_inner`) already matches MkDocs Material content; skip `--selector` unless you heavily customise templates.
    - When your site spans multiple documents, repeat the command per page and stitch them together with template slots (for example, `--slot mainmatter:build/site/manual/index.html`).
    - For live previews, point TeXSmith at the temporary site directory that `mkdocs serve` prints on startup.

    Once the LaTeX bundle looks good, add `--build` to invoke your engine of choice or wire it into CI so MkDocs HTML → TeXSmith PDF runs on every build.

## How does TeXSmith work?

TeXSmith ingests Markdown, HTML, YAML, and BibTeX, then runs them through a conversion pipeline to produce LaTeX or a finished PDF.

Templates define the layout and expose slots that get filled with content from your sources. The template manifest also lists compatible **fragments** that layer in extras such as a bibliography, glossary, fonts, page geometry, or other typesetting options.

![Workflow diagram of TeXSmith](../assets/workflow.drawio)

TeXSmith can render diagrams (Mermaid, Draw.io) into PDFs for inclusion in the LaTeX output. Choose between Tectonic, LuaLaTeX, or XeLaTeX depending on your typesetting needs.
