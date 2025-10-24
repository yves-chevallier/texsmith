# Texsmith MDPI Template

This package packages the MDPI article layout for [Texsmith](https://github.com/yves-chevallier/texsmith) and registers it under the `mdpi` entry point.

## Installation

```bash
# From the repository root
uv pip install ./templates/mdpi

# Once published
uv pip install texsmith-template-mdpi
```

## Usage

```bash
texsmith convert --template mdpi draft.md
```

## Template Details

- Engine: LuaLaTeX (shell escape required)
- TeX Live year: 2023
- tlmgr packages: `microtype`, `hyperref`, `geometry`, `booktabs`, `tcolorbox`, `algorithms`, `natbib`, `cleveref`, `listings`, `luatex85`
