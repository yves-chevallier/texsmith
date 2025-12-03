[](){ #releasenotes }
# Release Notes & Compatibility

Use this page to see what changed in each TeXSmith release and which LaTeX prerequisites (TeX Live year, `tlmgr` packages, shell-escape requirements) the bundled templates expect. Update your automation and CI images accordingly before bumping versions.

## TeXSmith releases

| Version | Highlights | Notes |
| ------- | ---------- | ----- |
| `0.1.0` | Unified conversion engine (`ConversionService`, `DocumentSlots`, diagnostics emitters), Typer CLI with `render`/`bibliography`, initial template catalog (article, book), diagram adapters (Mermaid, Draw.io, Svgbob), MkDocs integration hooks. | Requires Python 3.10+, MkDocs ≥ 1.6 for docs. Templates target TeX Live 2023. |
| `0.4.0` | Fragment manifest/ABC (attributes, partials, slot validation), explicit partial precedence (template > fragment > core), template discovery order (built-ins → packages → local → `~/.texsmith/templates`), improved `--template-info` output (slots, fragments, attribute columns). | Update custom fragments to `fragment.toml` + `partials`/`required_partials`; remove legacy template attributes (cover/twocolumn/backmatter/emoji) and use fragment-provided options instead. Use `texsmith templates` to confirm discovery. |

Future releases will append to this table with new features, migration notes, and API changes. If you upgrade past the compatibility range declared in a template manifest (`[compat]`), update the template and rerun its smoke tests.

## Template compatibility matrix

| Template | Version | TeX Live year | Shell escape | Key `tlmgr` packages | Notes |
| -------- | ------- | ------------- | ------------ | -------------------- | ----- |
| `article` | 0.1.0 | 2023 | Required (minted) | `babel`, `geometry`, `hyperref`, `microtype`, `lmodern`, `textcomp`, `fontspec`, `biblatex` | Provides `mainmatter` + `abstract` slots, ships custom `.latexmkrc` with minted settings. |
| `book` | 0.2.0 | 2023 | Required (minted) | `babel`, `babel-french`, `csquotes`, `fontspec`, `fancyvrb`, `geometry`, `hyperref`, `longtable`, `microtype`, `titlesec`, `titletoc`, `xcolor`, `xunicode` | Adds chapter-aware slots (`frontmatter`, `mainmatter`, `appendix`), reuses shared callouts/utility styles, ships cover assets. |

To inspect third-party or local templates, run:

```bash
texsmith --template <name-or-path> --template-info
```

The command lists TeX Live requirements, shell-escape expectations, slot definitions, and declared assets.

## Upgrade checklist

1. Run `uv run mkdocs build` to confirm docs compile without warnings on the new release.
2. Update your TeX Live image with any new packages referenced in the table above or in `template info`.
3. Rebuild the examples (`docs/examples/index.md`) and confirm smoke tests still pass.
4. Capture notable migrations (CLI flags, metadata schema changes) in this page and link PRs or release notes for future reference.
