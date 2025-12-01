# TeXSmith Book Template

The built-in `book` template ships with TeXSmith and focuses on long-form
documents with discrete front matter, multiple chapters, and appendices. It
wraps memoir defaults, modern callout styles, and the shared keystroke and
todo list helpers exported through `texsmith.templates.common`.

## Usage

```bash
texsmith manuscript.md --template book \
  --slot frontmatter:intro.md \
  --slot backmatter:appendix.md
```

## Template Details

- Engine: LuaLaTeX (shell escape required)
- TeX Live year: 2023
- tlmgr packages: `babel`, `babel-french`, `csquotes`, `fontspec`, `fancyvrb`, `geometry`, `hyperref`, `longtable`, `microtype`, `titlesec`, `titletoc`, `xcolor`, `xunicode`
