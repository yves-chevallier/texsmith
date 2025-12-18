# Getting Started

In our journey to typeset beautiful documents with TeXSmith, we'll start with the basics:

1. Turn Markdown or HTML into LaTeX/PDF.
2. Drop TeXSmith into an existing MkDocs site.
3. Drive it from Python.

Hop to the section you need or read straight through for the big picture.

## Installation

To install TeXSmith, use your preferred Python package manager:

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

For basic uses, you don't need anything else. TeXSmith bundles Tectonic for LaTeX builds and will auto-install the required tools on demand.

## Convert a Markdown file to LaTeX

By default TeXSmith writes LaTeX to stdout. Pipe it or direct it into a folder. HTML works too:

=== "Here document"

    ```text
    cat << EOF | texsmith
    # Title

    Some **bold** text.

    - Foo
    - Bar
    EOF
    \section{Title}\label{title}

    Some \textbf{bold} text.

    \begin{itemize}
    \item{} Foo
    \item{} Bar

    \end{itemize}
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

```yaml {.snippet caption="Demo" width="60%"}
cwd: ../../examples/booby
sources:
  - booby.md
```

Peek inside `build/` to find `booby.tex`. Swap `--template` when you want a different LaTeX project layout or polish level:

```bash
texsmith booby.md --template article --output-dir build
```

The default toolchain is `tectonic`, which auto-installs itself and required packages. If you prefer using your system LaTeX installation, specify `--engine lualatex` or `--engine xelatex` instead. Both commands yield `doc.pdf` in the current directory. Open it to see the rendered output.

If you want to customize the layout, choose a template with `--template article`, `--template book` or `--template your-own-template`.

You may want to pass additional LaTeX options such as `-apaper=a4` or `-amargin=1in` to tweak page geometry:

## Optional prerequisites

LaTeX distribution
: Install TeX Live, MiKTeX, or MacTeX if you want TeXSmith to hand off builds to `latexmk` (`--engine lualatex` / `--engine xelatex`). The default route uses Tectonic, which auto-installs itself and required packages.

Diagram tooling
: Mermaid-to-PDF (`minlag/mermaid-cli`) conversion falls back to Docker. Install Docker Desktop (with WSL integration on Windows) or register your own converter if Mermaid diagrams are common in your docs.

  Draw.io and Mermaid diagrams try a Playwright exporter first (cached under `~/.cache/texsmith/playwright`), then the local CLI, then Docker (`rlespinasse/drawio-desktop-headless` / `minlag/mermaid-cli`). Use `--diagrams-backend=playwright|local|docker` to pin a specific backend.

Fonts
: TeXSmith ships with Noto fallback for wide Unicode coverage. Add your own fonts if you want a specific script or branded look.

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

    The default selector (`article.md-content__inner`) already matches MkDocs Material content; skip `--selector` unless you heavily customise templates.

    When your site spans multiple documents, repeat the command per page and stitch them together with template slots (for example, `--slot mainmatter:build/site/manual/index.html`).

    For live previews, point TeXSmith at the temporary site directory that `mkdocs serve` prints on startup.

    Once the LaTeX bundle looks good, add `--build` to invoke your engine of choice or wire it into CI so MkDocs HTML → TeXSmith PDF runs on every build.
