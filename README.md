# TeXSmith

[![CI](https://github.com/yves-chevallier/texsmith/actions/workflows/ci.yml/badge.svg)](https://github.com/yves-chevallier/texsmith/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/yves-chevallier/texsmith/branch/main/graph/badge.svg)](https://codecov.io/gh/yves-chevallier/texsmith)
[![PyPI](https://img.shields.io/pypi/v/texsmith.svg)](https://pypi.org/project/texsmith/)
[![Repo Size](https://img.shields.io/github/repo-size/yves-chevallier/texsmith.svg)](https://github.com/yves-chevallier/texsmith)
[![Python Versions](https://img.shields.io/pypi/pyversions/texsmith.svg?logo=python)](https://pypi.org/project/texsmith/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)

![MkDocs](https://img.shields.io/badge/MkDocs-1.6+-blue.svg?logo=mkdocs)
![MkDocs Material](https://img.shields.io/badge/MkDocs%20Material-supported-success.svg?logo=materialdesign)
![LaTeX](https://img.shields.io/badge/LaTeX-API-lightgrey.svg?logo=latex)
![Python](https://img.shields.io/badge/Python-typed-blue.svg?logo=python)

TeXSmith is a [Python](https://www.python.org/) package and CLI tool to convert **Markdown** or **HTML** documents into LaTeX format. It is designed to be extensible via templates and integrates with [MkDocs](https://www.mkdocs.org/) for generating printable documents from documentation sites.

![TeXSmith Logo](docs/logo.svg)

## TL;DR

```bash
pip install texsmith
texsmith convert input.md input.bib -o article/ --template nature
```

## Render engine phases

The rendering pipeline walks the BeautifulSoup tree four times. Each pass maps
to a value of `RenderPhase` so handlers can opt into the point where their
transform should fire:

- `RenderPhase.PRE`: Early normalisation. Use it to clean the DOM and
  replace nodes before structural changes happen (e.g. unwrap unwanted tags,
  turn inline `<code>` into LaTeX).
- `RenderPhase.BLOCK`: Block-level transformations once the tree structure
  is stable. Typical consumers convert paragraphs, lists, or blockquotes into
  LaTeX environments.
- `RenderPhase.INLINE`: Inline formatting where block layout is already
  resolved. It is the right place for emphasis, inline math, or link handling.
- `RenderPhase.POST`: Final pass after children are processed. Use it for
  tasks that depend on previous passes such as heading numbering or emitting
  collected assets.
