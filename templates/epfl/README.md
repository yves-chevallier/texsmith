# Texsmith EPFL Thesis Template

This package exposes the EPFL thesis layout for [Texsmith](https://github.com/yves-chevallier/texsmith). It registers both `epfl` and `epfl-thesis` entry points for convenience.

## Installation

```bash
# From the repository root
uv pip install ./templates/epfl

# Once published
uv pip install texsmith-template-epfl
```

## Usage

```bash
texsmith convert --template epfl thesis.md
```

You can also pass `--template epfl-thesis` to target the same package.

## Template Details

- Engine: pdfLaTeX (shell escape required)
- TeX Live year: 2023
- tlmgr packages: `microtype`, `babel`, `fourier`, `lmodern`, `graphicx`, `xcolor`, `setspace`, `fancyhdr`, `booktabs`, `natbib`, `float`, `tikz`, `titlesec`, `hyperref`, `bookmark`, `subfig`, `minted`, `mathtools`, `amsmath`, `amssymb`, `amsfonts`
