# TeXSmith Book Template

The built-in `book` template targets long-form documents with front matter, chapters, appendices, and clean back matter. It wraps `memoir` defaults, modern callouts, keystroke helpers, todo lists, glossary/index hooks, and bibliography support.

## Usage

```bash
texsmith manuscript.md --template book \
  --slot frontmatter:intro.md \
  --slot backmatter:appendix.md
```

Slots:
- `frontmatter`, `preface`, `dedication`
- `mainmatter` (default)
- `appendix`
- `backmatter`, `colophon`

## Template Details

- Engine: LuaLaTeX
- TeX Live year: 2023
- tlmgr packages: `babel`, `babel-french`, `csquotes`, `fontspec`, `fancyvrb`, `geometry`, `hyperref`, `longtable`, `microtype`, `titlesec`, `titletoc`, `xcolor`, `xunicode`
- Built-in fragments: geometry, typesetting, fonts, extra, keystrokes, callouts, code, glossary, index, bibliography, todolist
- Attributes: title/subtitle/authors/email/date/language/documentclass, hyperref options, edition/publisher/imprint*, glossary toggles, list-of figures/tables, `part` flag for part/chapter structure.
- Assets: none (latexmkrc is injected by core).
