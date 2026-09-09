# Zensical compatibility notes

Findings recorded in September 2026 against Zensical 0.0.60, from its
documentation, its source (`python/zensical/`), and a trial build of this
documentation from the project's own `mkdocs.yml`. They inform the strategy for
producing a web site and a PDF from one source once MkDocs is no longer the
site generator.

## How Zensical works today

- Hybrid architecture: a Rust core (the ZRX scheduler, MiniJinja templates,
  the dev server) calls back into Python page by page to render Markdown. The
  whole rendering path is one function, `render(content, path, url, metadata)`
  in `python/zensical/markdown/render.py`, which instantiates Python-Markdown
  with the `markdown_extensions` of the configuration.
- Any importable Python-Markdown extension is accepted, from `zensical.toml`
  or from `mkdocs.yml`. The trial build confirmed it: `texsmith.index`,
  `texsmith.texlogos` and `texsmith.counters` emitted their markup
  (`ts-index`, `ts-hashtag`, `ts-counter`, `texlogo`) in the output.
- Fifteen MkDocs plugins are reimplemented natively (search, awesome-nav,
  literate-nav, autorefs, mkdocstrings, macros, markdown-exec, tags, meta,
  redirects, minify, glightbox, offline, section-index, table-reader). Every
  other plugin is **ignored silently**: `texsmith`, `drawio` and `pills` were
  skipped and the build reported "No issues found". The `.drawio` images were
  left as `<img src="x.drawio">`.
- `hooks:` is explicitly unsupported. There is no public Python API:
  `zensical.main` only defines the CLI, and nothing runs on the Python side
  after the Rust build returns.
- A module system shipped internally with ZRX 0.0.17 (March 2026) but is
  closed to third parties. The team ports the essential MkDocs plugins first,
  then plans a preview for the Spark community, then a public API with a
  Python binding. No date.
- PDF is absent from the roadmap. Backlog issue #25 ("support mkdocs-with-pdf")
  has been open since November 2025 without an answer.
- The search index is `site/search.json` (Disco format: `config` plus
  `items`), not lunr's `search_index.json`. `sitemap.xml` lists the pages in
  navigation order. The classic theme keeps Material's markup
  (`<article class="md-content__inner md-typeset">`).
- Announced for the coming year: a Rust parser "compatible with
  Python-Markdown", then a move to CommonMark. Custom Python-Markdown
  extensions may stop running on the web side at that point.

## Building this documentation with Zensical

`uv run --with zensical zensical build -f mkdocs.yml` succeeds (95 pages in
six seconds) after three changes to a copy of `mkdocs.yml`:

1. The YAML tag `!relative` (used for `pymdownx.snippets.base_path` and
   `pymdownx.blocks.html`) is not understood; replace it with a plain path.
2. `docs_dir` must live under the directory of the configuration file, and a
   symlink does not count.
3. The `autorefs` option `resolve_closest` is rejected.

## What breaks in TeXSmith

The `texsmith` MkDocs plugin relies on four hooks that Zensical does not have:
`on_config` (LaTeX configuration, language), `on_nav` (page order),
`on_post_page` (rendered HTML of each page) and `on_post_build` (book assembly
and compilation). `CountersPlugin` needs `on_nav` for its cross-page numbering
pre-pass and `on_page_content` to rewrite links. `IndexPlugin` rewrites
`search_index.json`, which no longer exists.

The part that does the actual work is already decoupled: `_render_book`
consumes HTML plus a flat navigation, and `render_with_fallback` turns HTML
into LaTeX.

## Strategy

1. **Make the book builder independent of the site generator.** Move it out
   of the MkDocs plugin into `texsmith.core` behind a command such as
   `texsmith site build [mkdocs.yml|zensical.toml]`: read the configuration
   (`nav`, `docs_dir`, `markdown_extensions`, `mdx_configs`, `site_name`,
   language), resolve awesome-nav's `.nav.yml` files, render each page with
   Python-Markdown and the same extension set, then reuse `_render_book`. The
   MkDocs plugin becomes a thin adapter. This works with MkDocs, with
   Zensical, or with no generator at all. The PDF is then built next to
   `zensical build`, not inside it. Post-processing `site/` (article
   extraction plus `sitemap.xml` order) is a fallback that recovers the exact
   site HTML, at the price of depending on the theme markup.
2. **Replace hooks by self-sufficient Python-Markdown extensions on the web
   side.** Rendering runs in the same interpreter as the configuration, so an
   extension can call `zensical.config.get_config()` to obtain `nav` and
   `docs_dir`, perform the counter pre-pass once per process, and rewrite
   cross-page `href`s in a tree processor. `ContextExtension` injects the page
   context (`url`, `path`, `meta`). Feeding index entries into the search
   index is lost until the module API exists.
3. **A native Zensical module in the long run**, consuming the
   `RenderedMarkdown` artifacts and the navigation and producing the `.tex`
   and the PDF as outputs with differential builds. Cheap action now: follow
   backlog issue #25 and the Spark programme to be among the ecosystem
   maintainers invited to the API preview.

Side decisions: drop the `!relative` tags and `resolve_closest` from
`mkdocs.yml` or keep a `zensical.toml` variant, add a non-blocking
`zensical build` job in CI, pre-render draw.io and Mermaid diagrams on the
TeXSmith side since their MkDocs plugins do not exist under Zensical, and treat
the CommonMark switch as the reason for TMark's canonical form and
`tmark fmt --profile mkdocs`: the site receives Markdown any parser
understands, TeXSmith keeps its own parser for the PDF.

## Sources

- [Roadmap](https://zensical.org/about/roadmap/),
  [supported MkDocs plugins](https://zensical.org/compatibility/plugins/),
  [migration guide](https://zensical.org/docs/compatibility/mkdocs/migration/),
  [customisation](https://zensical.org/docs/customization/)
- [ZAP 007, module system](https://zensical.org/spark/proposals/zap-007-module-system/),
  [March 2026 newsletter](https://mail.zensical.org/monthly/2026/03/index.html)
- [`render.py`](https://github.com/zensical/zensical/blob/master/python/zensical/markdown/render.py),
  [`config.py`](https://github.com/zensical/zensical/blob/master/python/zensical/config.py),
  [releases](https://github.com/zensical/zensical/releases)
- [Backlog #25, mkdocs-with-pdf](https://github.com/zensical/backlog/issues/25)
