# Texsmith Article Template

This package bundles the `article` layout for [Texsmith](https://github.com/yves-chevallier/texsmith). Installing it makes the template discoverable through the `texsmith.templates` entry point group.

## Installation

```bash
# From the repository root
uv pip install ./templates/article

# Once published
uv pip install texsmith-template-article
```

## Usage

Invoke Texsmith with the registered entry point:

```bash
texsmith convert --template article README.md
```

## Template Details

- Engine: LuaLaTeX (shell escape required)
- TeX Live year: 2023
- tlmgr packages: `babel`, `geometry`, `hyperref`, `microtype`, `fontspec`
