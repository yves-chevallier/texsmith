# Texsmith Nature Template

The Nature SN article layout is published through this package and exposed to [Texsmith](https://github.com/yves-chevallier/texsmith) under both `nature` and `sn-article` entry points.

## Installation

```bash
# From the repository root
uv pip install ./templates/nature

# Once published
uv pip install texsmith-template-nature
```

## Usage

```bash
texsmith convert --template nature paper.md
```

`--template sn-article` is also accepted.

## Template Details

- Engine: LuaLaTeX (shell escape required)
- TeX Live year: 2023
- tlmgr packages: `hyperref`, `microtype`, `booktabs`, `tcolorbox`, `minted`, `algorithms`, `fontspec`
