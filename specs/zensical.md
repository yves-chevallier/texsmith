# Zensical compatibility notes

Findings recorded on 2026-09-09 against Zensical 0.0.60, from its
documentation, its source (`python/zensical/`), and a trial build of this
documentation from the project's own `mkdocs.yml`. They inform the strategy for
producing a web site and a PDF from one source once MkDocs is no longer the
site generator.

## What the TMark migration changed under this note

The note predates TeXSmith 0.7.0 and describes the Python-Markdown pipeline it
replaced. Three of its premises no longer hold, and each of them makes the
strategy below *easier*, not harder:

- **TeXSmith no longer renders through HTML.** `render_with_fallback` and the
  HTML reader are deleted; a Markdown source is parsed by `tmark.parse` and
  written by the tmark writers. So the book builder does not need the site
  generator's HTML at all — the item 1 fallback ("post-process `site/`") is
  no longer a fallback worth keeping.
- **The web side is one function, not a set of extensions.** The three
  `markdown.extensions` entry points the trial build exercised
  (`texsmith.index`, `texsmith.texlogos`, `texsmith.counters`) are gone; the
  single `texsmith` plugin lowers a page with `tmark.lower_web`, which is Rust
  and has no Python-Markdown dependency. Item 2 becomes "call `lower_web`
  wherever the generator lets us", which is a much smaller surface.
- **Zensical's announced move to a CommonMark parser stops being a threat.**
  The site now receives Markdown that any CommonMark parser reads, because
  that is what `lower_web` emits; TeXSmith keeps its own parser for the PDF.

What survives unchanged: the hook inventory (Zensical has none of the four the
plugin uses), the absence of a public module API, the state of backlog issue
\#25, and the side decisions at the end.

Item 1 of the strategy is done, in the shape the three premises above allow:
the book builder is `texsmith.site.book` and the command is `texsmith site
build [CONFIG]`. It reads no HTML — `_render_book` and `render_with_fallback`
are gone, and each page reaches the book as the Markdown it is written in,
through the tmark reader — and it takes the navigation of
`texsmith.site.nav`, the resolver that reads `.nav.yml` itself. The MkDocs
plugin is the thin adapter the item asked for: it converts its own navigation
and calls the same builder, and the `.tex` of the two paths is identical.

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

**2026-09-16, Zensical 0.0.62.** The list has shrunk to its first two items,
and the configuration this documentation is built from is `mkdocs.yml` itself.
`zensical/config.py` loads it with the full `yaml.Loader`, so a
`!!python/name:` tag resolves; it registers an `!ENV` constructor of its own;
it rewrites `material.extensions` to `zensical.extensions` before parsing; and
`resolve_closest` is listed among `autorefs`' recognised-but-unimplemented
options, so it is accepted and dropped rather than rejected (item 3). Item 1
stands: no `!relative` constructor is registered, and that is the single
adaptation left. Item 2 stands as well — `docs_dir` is resolved and must be
`is_relative_to` the project root, so a symlink still does not count.

## What breaks in TeXSmith

The `texsmith` MkDocs plugin relies on four hooks that Zensical does not have:
`on_config` (LaTeX configuration, language), `on_nav` (page order),
`on_post_page` (rendered HTML of each page) and `on_post_build` (book assembly
and compilation). `CountersPlugin` needs `on_nav` for its cross-page numbering
pre-pass and `on_page_content` to rewrite links. `IndexPlugin` rewrites
`search_index.json`, which no longer exists.

The part that does the actual work is already decoupled: the book renderer
consumes HTML plus a flat navigation, and `render_with_fallback` turns HTML
into LaTeX. (Both are gone since; see the section above.)

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

## What shipped, and what the handbook taught (2026-09-16)

Strategies 1 and 2 are implemented on the `zensical` branch: `texsmith.site`
(index, config, nav, book, search, assets, web) is the site machinery, the
MkDocs plugin is an adapter over it, and `texsmith.site.web` is the
Python-Markdown extension Zensical runs. Two facts of Zensical's build model
shaped the design more than any hook inventory:

- **Zensical clears `site_dir` on every build and, on a warm `.cache/`,
  never calls Python at all.** A render-time side effect (a stylesheet, a
  snippet preview written into `site_dir`) therefore exists only after a
  cold-cache build. Generated files must be *sources* under `docs_dir`,
  produced before the build: that is `texsmith site assets`, and the reason
  `make docs-zensical` chains `assets → build → search → site build`. A file
  written into `docs_dir` during a render is published one build later, which
  is what makes `zensical serve` pick up an edited snippet.
- **The Python side sees no navigation.** awesome-nav is resolved in Rust and
  `get_config()["nav"]` is `[]`, so `texsmith.site.nav` resolves `.nav.yml`
  itself (verified identical to MkDocs + awesome-nav on two sites). Zensical
  arms awesome-nav on plugin *presence*: a site that lists only
  `awesome-pages` gets an alphabetical, untitled navigation until
  `awesome-nav` is declared too.

The second corpus, the HEIG-VD handbook (142 pages, French, two PDF books,
six MkDocs hooks, awesome-pages, TeXSmith 0.2.1), was migrated on its own
`zensical` branch and reached `zensical build` with no issue, a search index
carrying its entries, and two compiling books (647 and 64 pages, the C book
on its own cover and with a printed index). What it taught, by layer:

- **Zensical itself** needs no configuration change for such a site (full
  `yaml.Loader`, its own `!ENV`, `material.extensions` remapped). It ignores
  `exclude_docs`, `hooks:` and every unknown plugin silently, so include
  sources under `docs/` become orphan pages and nothing on our side can stop
  it. Its search engine indexes `tags` only as a filter facet: the index
  entries go into `text`.
- **TeXSmith, template and build.** The `book` template did not compile in
  French at all (`fixtoc.sty` measured `\partname` under `babel-french`
  before the counter existed, twice); lists stopped at four levels; the book
  compiled without the `features` that run biber/makeindex, so `\printindex`
  was empty; root-relative `/assets/…` paths and an undeclared snippet
  `base_path` were resolved against the wrong directory; `\newacronym` was
  emitted twice per acronym under a folded key; callout titles were English
  whatever `language:` said; keystrokes did not survive a PDF bookmark;
  `copy_files` could copy a title page nothing consumed (`press.titlepage`,
  `press.imprint`, `press.preamble` are the answer, with the `file` attribute
  format).
- **TeXSmith, site.** The pre-pass parsed a page's *body* and attached its
  front matter afterwards, so a page's own `press.declare` never reached the
  parser; `lower_web` received no `Loader` for fence includes; `auto_append`
  was honoured by nobody; a `.drawio` image was redirected but not the
  lightbox anchor around it; `\|` inside a code span of a table cell reaches
  the site with its backslash (Python-Markdown's, unescaped in our
  postprocessor).
- **tmark.** The autorefs idiom (`[](){#id}` + `[text][id]`) was invisible on
  both media: the anchor lowered to raw HTML no tree scanner sees, and the
  reference-style link had no reading (spec §Ref gained one). Fragment spans
  were relative to the fragment, not the file, which mislocated a counter in a
  `!!!` title and a code span in a `yaml table` cell. Label names were
  escaped as prose (`\hyperref[a\_b]`). A literal `[` opening a table cell
  read as `\\[dimen]`. Material's braces-only fence info (`{ .c .annotate }`)
  parsed `{` as the language with no diagnostic. `/// html | div[…]`
  containers and fence `include=` were dropped on the web.
- **The corpus.** Every wiki-link `[[tag]]`, epigraph key, `.pages` file,
  spantable marker and translated admonition title had a TMark spelling; the
  migration is scripted (`utils/` in the handbook) and idempotent. Two
  constructs have none yet: the `exercises` plugin's quizzes (`- [x]`) and
  fill-in-the-blanks (`{{word}}`), and per-page numbering (TMark counters are
  site-wide).

Still open after this round: `mike` versioning has no Zensical equivalent;
`mkdocs-caption` is a plugin, so a plain `![alt](img)` is a bare `<img>` on the
web with no numbered caption (the PDF numbers its figures itself); an
abbreviation key such as `UTF-8`, `EOF`, `W3C` does not reach the glossary
(4 of the handbook's 44);
`<p class="admonition-title">` carries no `markdown` attribute, so Markdown
inside a rewritten callout title does not render; box-drawing glyphs in code
blocks have no coverage in the monospace font (7 831 missing characters in
the C book); `texsmith.site.nav` reimplements wcmatch, natsort and pathspec
rather than depending on them; and every core fix lives on tmark's
`autorefs-anchors` branch behind an unstaged `[tool.uv.sources]` override,
which a `tmark-core` release must replace before the TeXSmith branch merges.

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
