# TeXSmith Article Template

This directory hosts the built-in `article` layout bundled with [TeXSmith](https://github.com/yves-chevallier/texsmith). The CLI exposes it via `--template article` (or `-tarticle`), so no extra installation is required.

```bash
texsmith intro.md --template article --output-dir build/article
```

To customise the template, copy this directory (or extract it via `importlib.resources`) and adjust the manifest, assets, or LaTeX entry point before packaging it as your own distribution.

## Fonts

Markdown is usually rendered on web broswers that supports a wide range of unicode characters. In LaTeX few fonts support such a wide range of characters. This template uses the most comprehensive font available: [Noto](https://notofonts.github.io/). However you need to install the font on your system first. You can download it from [Google Fonts](https://fonts.google.com/noto) or install it through your system package manager. For example on Ubuntu:

```bash
sudo apt update
sudo apt install fonts-noto-core
sudo apt install fonts-noto-cjk
sudo apt install fonts-noto-extra
```

For black and white emojis, the `Symbola` font is used. For example on Ubuntu:

```bash
sudo apt update
sudo apt install fonts-symbola
```

## Template Details

- Engine: LuaLaTeX (shell escape required)
- TeX Live year: 2023
- tlmgr packages: `babel`, `geometry`, `hyperref`, `microtype`, `fontspec`
