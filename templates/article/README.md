# Texsmith Article Template

This package bundles the `article` layout for [Texsmith](https://github.com/yves-chevallier/texsmith). Installing it makes the template discoverable through the `texsmith.templates` entry point group.

## Installation

```bash
# From the repository root
uv pip install ./templates/article

# Once published
uv pip install texsmith-template-article
```

## Fonts

Markdown is usually rendered on web broswers that supports a wide range of unicode characters. In LaTeX few fonts support such a wide range of characters. This template uses the most comprehensive font available: [Noto](https://notofonts.github.io/). However you need to install the font on your system first. You can download it from [Google Fonts](https://fonts.google.com/noto) or install it through your system package manager. For example on Ubuntu:

```bash
sudo apt update
sudo apt install fonts-noto-core
sudo apt install fonts-noto-cjk
sudo apt install fonts-noto-extra
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
