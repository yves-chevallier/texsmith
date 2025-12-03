# TeXSmith

Of course, this documentation itself can be converted into a LaTeX document using TeXSmith!

```bash
git clone https://github.com/yves-chevallier/texsmith.git
cd texsmith
uv sync --with docs
export TEXSMITH_MKDOCS_BUILD=1 # Enable PDF build
uv run texsmith mkdocs build
```
