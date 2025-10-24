# Texsmith Caraumã Template

This package publishes the Caraumã-inspired book layout for [Texsmith](https://github.com/yves-chevallier/texsmith). Installing it registers both `carauma` and `carauma-book` entry points so the template can be selected by slug or by its manifest name.

## Installation

```bash
# From the repository root
uv pip install ./templates/carauma

# Once published
uv pip install texsmith-template-carauma
```

## Usage

```bash
texsmith convert --template carauma drafts/manuscript.md
```

Both `--template carauma` and `--template carauma-book` resolve to this package.

## Template Details

- Engine: LuaLaTeX (shell escape required)
- TeX Live year: 2023
- tlmgr packages: `microtype`, `babel`, `lettrine`, `graphicx`, `xcolor`, `fontspec`, `ebgaramond`, `pgf`, `geometry`, `tocloft`, `titlesec`, `fancyhdr`, `float`, `booktabs`, `tcolorbox`, `minted`
