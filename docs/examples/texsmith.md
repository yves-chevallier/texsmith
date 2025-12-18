# TeXSmith

And of course, the grand finale -- the true climax of the project -- is that this very documentation can itself be converted into a LaTeX document using TeXSmith.

```bash
git clone https://github.com/yves-chevallier/texsmith.git
cd texsmith
uv sync --with docs
export TEXSMITH_MKDOCS_BUILD=1 # Enable PDF build
uv run texsmith mkdocs build
```

You can download it directly from the [release page](https://github.com/yves-chevallier/texsmith/releases).
