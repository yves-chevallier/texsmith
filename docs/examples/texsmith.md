# TeXSmith

Of course, this documentation itself can be converted into a LaTeX document using TeXSmith!

```bash
git clone https://github.com/yves-chevallier/texsmith.git
cd texsmith
uv sync --with docs
uv run texsmith mkdocs build
cd build
latexmk --shell-escape texsmith-docs.tex
```

The configuration is done in `mkdocs.yml`, using the special `__texsmith_full_navigation__`
