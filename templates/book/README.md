# Texsmith Book Template

The `book` template extends Texsmith with a multi-chapter layout featuring dedicated title, imprint, and cover assets. Installing this package registers the template in the `texsmith.templates` entry point group.

## Installation

```bash
# From the repository root
uv pip install ./templates/book

# Once published
uv pip install texsmith-template-book
```

## Usage

```bash
texsmith convert --template book docs/manuscript.md
```

## Template Details

- Engine: LuaLaTeX (shell escape required)
- TeX Live year: 2023
- tlmgr packages: `babel`, `babel-french`, `csquotes`, `fontspec`, `fancyvrb`, `geometry`, `hyperref`, `longtable`, `microtype`, `titlesec`, `titletoc`, `xcolor`, `xunicode`
