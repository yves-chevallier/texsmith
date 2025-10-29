# Getting Started

Use this guide to install TeXSmith, verify the CLI, and explore the Python API.
Once you can render a single Markdown page, jump to the CLI or API sections for
the deeper feature set.

## Prerequisites

- **Python 3.10+** – TeXSmith ships as a Python package. We recommend
  [uv](https://github.com/astral-sh/uv) or `pipx` for isolated installs.
- **LaTeX distribution** – Install TeX Live, MiKTeX, or MacTeX so `texsmith render --build`
  can call `latexmk` and friends.
- **Optional diagram tooling** – Mermaid-to-PDF conversion defaults to Docker
  (`minlag/mermaid-cli`). Install Docker Desktop (with WSL integration on
  Windows) or register your own converter if you rely on Mermaid diagrams.

!!! tip
    Containerised TeX Live images work fine—mount your project into the
    container and run `texsmith render --build` inside.

## Install TeXSmith

=== "uv"
    ```bash
    uv tool install texsmith
    ```

=== "pip / pipx"
    ```bash
    pip install texsmith
    # or
    pipx install texsmith
    ```

Optionally install template packages such as `texsmith-template-nature` from
PyPI when you need layout presets tailored to journals or publishers.

## Try the CLI

```bash
cat <<'EOF' > intro.md
# Sample report

Numbers appear in @tbl:summary.

| Item | Value |
|------|------:|
| Foo  |  42.0 |
| Bar  |   3.1 |
{: #tbl:summary caption="Key metrics"}
EOF

texsmith render intro.md --output build/
ls build
```

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

## Next steps

- Read the [Command-line overview](../cli/index.md) for every flag and
  subcommand.
- Explore [High-Level Workflows](../api/high-level.md) to orchestrate templates
  programmatically.
- Browse [Supported Markdown Syntax](../markdown/supported.md) to see exactly
  which extensions TeXSmith enables by default.
