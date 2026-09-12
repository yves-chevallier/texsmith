[](){ #releasenotes }
# Release Notes & Compatibility

Use this page to see what changed in each TeXSmith release, what the current
architecture is, and which LaTeX prerequisites (TeX Live year, `tlmgr`
packages, shell-escape requirements) the bundled templates expect. Update your
automation and CI images accordingly before bumping versions.

The narrative record of every release is `CHANGELOG.md` at the root of the
repository; this page is the compatibility summary that goes with it.

## What TeXSmith is made of today

TeXSmith reads **TMark** — CommonMark plus the extension set every MkDocs site
already uses, plus the constructs a printed document needs — and it does so
with the TMark parser, not with Python-Markdown. A conversion runs in four
steps:

1. `tmark.parse` turns the source into the document IR.
2. TeXSmith's **passes** do the work that needs a file, a clock, a process or a
   socket: `include`, `snippet`, `assets` (diagram and image conversion),
   `highlight` (Pygments), `doi`, `emoji`, `scripts`, `var`, `title`, `slots`,
   `headings`, `glossary`.
3. `tmark.resolve` allocates the numbers and resolves every `@` reference,
   reading the `.bib` files and the `refs.json` inventories through a loader
   TeXSmith supplies.
4. `tmark.write` emits the LaTeX and Typst bodies; `tmark.lower_web` emits the
   HTML a MkDocs page shows.

Everything else is still TeXSmith's: templates, fragments, fonts, the engines
(Tectonic, latexmk, Docker), bibliography output, the cross-reference inventory
writer, the CLI and the MkDocs plugin.

Each construct in a body is **one contract macro** — `\tscallout`, `tscode`,
`\tskeys`, `\tslead`, `\tsaside`, `\tsindex`, … — defined by the `ts-*`
fragment that the body's `Requires` pulls into the preamble, with
`templates/common/texsmith.typ` as the Typst mirror. Redefining that macro in
your template is how you restyle a construct; the Jinja partial mechanism, the
`latex.template.override` hook, `partials` / `required_partials` and the
template-scoped `readers` / `writer` hooks no longer exist. See
[Templates](../guide/templates/partials.md) for the former-partial → macro map.

## TeXSmith releases

| Version | Highlights | Notes |
| ------- | ---------- | ----- |
| `0.1.0` | Unified conversion engine (`ConversionService`, slot assignments, diagnostics emitters), Typer CLI with `render`/`bibliography`, initial template catalog (article, book), diagram adapters (Mermaid, Draw.io, Svgbob), MkDocs integration hooks. | Requires Python 3.10+, MkDocs ≥ 1.6 for docs. Templates target TeX Live 2023. |
| `0.4.0` | Fragment manifest/ABC (attributes, partials, slot validation), explicit partial precedence (template > fragment > core), template discovery order (built-ins → packages → local → `~/.texsmith/templates`), improved `--template-info` output (slots, fragments, attribute columns). | Historical: the `partials` / `required_partials` keys this release introduced are removed in the TMark release below. Template discovery and `fragment.toml` attributes are unchanged. |
| `0.5.0` | `@[label]` cross-reference shorthand; Typst cross-reference targets (heading, figure and table labels). | `@[…]` is now spelled `@label`; both are read. |
| `0.6.0` | Custom counters, cross-document references (`<document>.refs.json` inventories, `crossrefs:`), inline-code wrapping (`code.inline`), draw.io page-size export (`crop=false`). | Last release on the Python-Markdown pipeline. A document written for 0.6 still builds; run `tmark lint --fix` to move it to the canonical spellings. |
| *Unreleased* | TeXSmith reads Markdown with the TMark parser and writes its LaTeX, Typst and HTML bodies with the TMark writers. A construct is a contract macro a `ts-*` fragment provides. One MkDocs plugin numbers a site and its PDF export alike. Diagnostics have one shape, a position, `--strict` and `--diagnostics-json`; `--numbering` and `--deprecated` are new. | The Python-Markdown pipeline, its 17 extensions, the Python writers, the hand-written IR and the 45 Jinja partials are removed, and with them `--reader`, `--html`, `--debug-html`, `--list-extensions`, `-x` / `-X` and the four template hooks. Read [Migrating to TMark](../guide/migration.md) first; `tmark lint --fix` does the mechanical rewrites. |

If you upgrade past the compatibility range declared in a template manifest
(`[compat]`), update the template and rerun its smoke tests.

## Supported syntax

The dialect is specified, not accumulated from whichever plugins happen to be
installed: [Syntax](../syntax/index.md) is the reference, and
[Supported constructs](../syntax/supported.md) is the per-construct table.
Three things are worth knowing before you upgrade:

- **The 0.6 spellings still parse.** Most of them are deprecated sugar with a
  stated horizon; `tmark lint` names each one and `tmark lint --fix` rewrites
  the mechanical ones in place. The spellings MkDocs Material or Pandoc renders
  natively (`!!! note`, `=== "Tab"`, `<div markdown>`, `~~del~~`, `==mark==`,
  `++Ctrl+C++`, `:smile:`, a bare ```` ```mermaid ```` fence) are kept
  indefinitely.
- **A CommonMark parser reads a few things differently**, and no fixer can
  repair that: lazy continuation lines, list indentation to the parent's
  content column, no emphasis inside a word, HTML block boundaries, entity
  decoding, and attribute lists that need a host. The list is in
  [Migrating to TMark](../guide/migration.md).
- **Critic markup is not lowered yet.** `{++added++}`, `{--removed--}`,
  `{~~old~~new~~}` and `{>>comment<<}` stay literal text and raise
  `compat-unsupported`, so a `--strict` run catches them. The `ts-critic`
  fragment already defines `\tsins`, `\tsdel`, `\tssubst` and `\tscomment` for
  the day the writers emit them.

## Template compatibility matrix

| Template | Version | TeX Live year | Shell escape | Key `tlmgr` packages | Notes |
| -------- | ------- | ------------- | ------------ | -------------------- | ----- |
| `article` | 0.1.0 | 2023 | Only with `code.engine: minted` | `babel`, `geometry`, `hyperref`, `microtype`, `lmodern`, `textcomp`, `fontspec`, `biblatex` | Provides `mainmatter` + `abstract` slots, ships a custom `.latexmkrc`. |
| `book` | 0.2.0 | 2023 | Only with `code.engine: minted` | `babel`, `babel-french`, `csquotes`, `fontspec`, `fancyvrb`, `geometry`, `hyperref`, `longtable`, `microtype`, `titlesec`, `titletoc`, `xcolor`, `xunicode` | Adds chapter-aware slots (`frontmatter`, `mainmatter`, `appendix`), reuses shared callouts/utility styles, ships cover assets. Redefines `\tscodeinline` after `\VAR{extra_packages}`, which is the supported way to restyle a construct. |

Neither bundled template declares `shell_escape` any more: the generated
`.latexmkrc` turns `--shell-escape` on only when `code.engine` is `minted`, and
the default engine is `pygments`, which pre-renders the highlighting in Python.
A document that never asks for `minted` therefore compiles in a sandbox that
forbids shell escape.

To inspect third-party or local templates, run:

```bash
texsmith --template <name-or-path> --template-info
```

The command lists TeX Live requirements, shell-escape expectations, slot
definitions, and declared assets.

## Upgrade checklist

1. Run `tmark lint --fix --diff` over your sources, read the diff, then apply
   it on a clean tree.
2. Convert with `--strict` (or `press.features.strict: true`) once, and read
   what it reports; `--deprecated info` keeps the legacy-spelling warnings out
   of the gate while you work through the rest.
3. If you maintain a template or a fragment, replace every `partials`,
   `required_partials`, `override`, `readers` and `writer` declaration with a
   redefinition of the contract macro
   ([map](../guide/templates/partials.md)).
4. Drop `texsmith.*` entries from `markdown_extensions:` in `mkdocs.yml`,
   replace the `texsmith.counters` and `texsmith.index` plugins with the single
   `texsmith` plugin, and move any `counters:` under its `declare.counters`.
5. Run `uv run mkdocs build` to confirm the docs compile without warnings on
   the new release.
6. Update your TeX Live image with any new packages referenced in the table
   above or in `--template-info`.
7. Rebuild the examples (`docs/examples/index.md`) and confirm the smoke tests
   still pass.
