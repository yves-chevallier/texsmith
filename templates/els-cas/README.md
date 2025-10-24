# Texsmith Elsevier CAS Template

This package registers the Elsevier CAS article layout for [Texsmith](https://github.com/yves-chevallier/texsmith) under the `els-cas` entry point.

## Installation

```bash
# From the repository root
uv pip install ./templates/els-cas

# Once published
uv pip install texsmith-template-els-cas
```

## Usage

```bash
texsmith convert --template els-cas manuscript.md
```

## Template Details

- Engine: LuaLaTeX (shell escape required)
- TeX Live year: 2023
- tlmgr packages: `fontspec`, `hyperref`, `microtype`, `booktabs`, `tcolorbox`, `minted`, `algorithms`, `natbib`
