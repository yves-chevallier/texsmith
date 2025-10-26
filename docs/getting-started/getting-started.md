# Getting Started

## Install

To install TeXSmith, you can use `pip` or even `pipx`[^pipx] if you only need the command line tool:

```bash
pip install texsmith
```

To generate beautiful LaTeX forged documents you will also need to have a LaTeX distribution installed on your system. Popular distributions include TeX Live (cross-platform), MiKTeX (Windows), and MacTeX (macOS). On Ubuntu if you are not too picky you can install the full TeX Live distribution with:

```bash
sudo apt install texlive-full
```

!!! note
    A Docker image of TeXLive would also work fine if you prefer containerized applications.


Now you are almost ready to use TeXSmith. Yet you may need a template. TeXSmith is shipped with a default template, but you can also create your own or use TeXSmith templates shared by the community. Let's imagine you want to write a Nature article. You can install the `texsmith-template-nature` template from PyPI with:

```bash
pip install texsmith-template-nature
```

## Basic Usage

Once TeXSmith is installed, you can convert a Markdown file to LaTeX by running the following command in your terminal:

```bash
texsmith convert input.md -o output.tex
```

With a template of your choice, you can specify it with the `--template` option:

```bash
texsmith convert input.md -o output.pdf --template nature
```

With scientific documents you may want to include citations and a bibliography. TeXSmith supports this feature using a BibTeX file. You can specify the bibliography file with the `--bibliography` option:

```bash
texsmith convert input.md references.bib -o output.pdf --template nature
```

## Programmatic Usage

Prefer to stay in Python?  The high-level API mirrors the CLI and handles all the boilerplate for you:

```python
from pathlib import Path

from texsmith import Document, convert_documents

bundle = convert_documents(
    [
        Document.from_markdown(Path("intro.md")),
        Document.from_html(Path("appendix.html")),
    ],
    output_dir=Path("build"),
)

print("Combined LaTeX:\n", bundle.combined_output())
```

For template-centric workflows, reach for `texsmith.TemplateSession`.  The [API guide](../api/high-level.md) walks through end-to-end examples.

[^pipx]: [pipx](https://pipx.pypa.io/stable/) is a recent tool used to leverage requirements of PEP 660 (i.e. install and run Python applications in isolated environments). It is very convenient to install command line tools without polluting your main Python environment.
