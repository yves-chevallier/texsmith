# Integration with MkDocs

One plugin, `texsmith`, carries the whole integration: it renders the TMark
constructs on the site *and* exports the same sources as a PDF. Add it to
`mkdocs.yml` and nothing else:

```yaml
plugins:
  - search
  - texsmith
```

No Markdown extension to wire by hand. The plugin turns on the five extensions
its output relies on — `attr_list`, `md_in_html`, `admonition`,
`pymdownx.details` and `pymdownx.superfences` — when they are absent, and ships
a small stylesheet (`assets/texsmith/texsmith.css`: asides, the subfigure grid,
caption labels, counter spans) through `extra_css`. Set
`inject_markdown_extensions: false` or `css: false` to take either over.

!!! warning "The `texsmith.counters` and `texsmith.index` plugins are gone"
    Both jobs belong to `texsmith` now. The two entry points still load, log a
    warning and do nothing; they disappear in 0.8. Remove them from `plugins:`
    and move any `counters:` you declared under them to `declare.counters`
    (below).

## What the plugin does to a page

Before Python-Markdown runs, every page goes through `tmark`:

1. a **pre-pass** parses and resolves every page in navigation order, chaining
   the counters from one page to the next, and collects the labels of the whole
   site;
2. each page is then resolved again against that site map and **lowered**: each
   TMark construct is replaced by the Markdown or HTML Material renders — a
   callout becomes an admonition, a figure a `<figure>`, a counter item a
   `<span class="ts-counter">` — and every other byte is left alone.

So Material's own syntax (`++ctrl+alt+del++`, `==marked==`, tab sets, emoji,
mermaid fences, an `mkdocstrings` block) passes through untouched, and a
construct TeXSmith owns renders the same way it does in the PDF.

Diagnostics are reported with the page path: `docs/findings.md:12:5: warning
ref-unresolved: …`.

## French typography

A French page wants a narrow no-break space before `;`, `:`, `!` and `?`, and
`« … »` where the keyboard typed `"…"`. `babel-french` does it for the PDF,
where the engine spaces the punctuation itself; a browser does nothing of the
sort, so the rendered page carries the characters. Once the site's language is
`fr` — `theme.language`, `theme.locale`, `site_language` or the plugin's own
`language` — the rendered HTML goes through those two rules:

| Written | Published |
| --- | --- |
| `Attention : ceci` | `Attention` U+202F `: ceci` |
| `Vraiment ?` | `Vraiment` U+202F `?` |
| `il a dit "oui"` | `«` U+202F `oui` U+202F `»` |

Only text is touched. A `<code>`, `<pre>`, `<script>` or `<style>` element,
every attribute value, every character entity and every space the page already
carries — `&nbsp;`, a narrow one — come out as they went in, and a mark that is
part of a token rather than of a sentence (`https://`, `12:30`, `?page=2`) is
left alone. Running the rules over a page twice changes nothing the second
time.

`web.typography` overrides the language: `none` turns the rules off on a French
site, `fr` turns them on for a site that declares another language.

```yaml
plugins:
  - texsmith:
      web:
        typography: fr # fr | none, the site language by default
```

Under Zensical the spaces are part of a page's cached render, so changing the
option calls for `zensical build -c`.

## Site-wide declarations

Whatever a page declares under `press.declare` in its front matter, the
plugin's `declare:` key declares for every page of the site — counters,
callout kinds, glossary terms:

```yaml
plugins:
  - texsmith:
      declare:
        counters:
          req:
            name: Requirement
            format: "REQ-{n:03d}"
            start: 100
        admonitions:
          exercise:
            name: Exercise
```

A page may still declare its own in its front matter; the page's declaration
wins over the site's, kind by kind and name by name, and the two sets merge.
See [Counters](../syntax/counters.md) for the numbering rules.

Both reach the **parser**, not only the renderer, so a callout kind declared
here is one `::: exercise` can be spelled with anywhere on the site — on the
web and in the books alike. A kind nothing declares is `container-unknown`
and its fence stays literal text on the page.

## Options

| Option | Description | Default |
| --- | --- | --- |
| `enabled` | Turn the plugin off entirely | `true` |
| `template` | Template used for the books | `book` |
| `build_dir` | Where the `.tex`, the assets and the PDF land | `press` |
| `declare` | Site-wide declarations (`declare.counters`, `declare.admonitions`, `declare.glossary`) | `{}` |
| `web` | Web-only options: `sections` (`title` \| `number`), `citations` (`inline` \| `passthrough`), `css_prefix`, `tags` (`index` \| `none`) and `typography` (`fr` \| `none`) | `{}` |
| `inject_markdown_extensions` | Enable the extensions the lowering relies on | `true` |
| `css` | Ship and register `texsmith.css` | `true` |
| `language` | Document language, else the theme's | *theme* |
| `bibliography` | `.bib` files shared by every book | `[]` |
| `books` | The documents to export (below) | `[]` |
| `template_overrides` | Template attributes for every book | `{}` |
| `copy_assets` / `clean_assets` | Copy the referenced assets / prune the unused ones | `true` |
| `embed_documents` | Inline each page's body instead of `\input` | `false` |

## Books

A book is one PDF built from a section of the navigation. Several may be
declared; `root: "__texsmith_full_navigation__"` takes the whole site. Without
an explicit `books:` entry, the plugin creates one book automatically, using
only the first item of the site's navigation as its root section — every other
page is left out of that default book. Declare `books:` explicitly, with
`root: "__texsmith_full_navigation__"` on the one entry, to get the whole site
as a single book instead.

```yaml
plugins:
  - texsmith:
      books:
        - template: book
          title: "Foo, the complete guide"
          folder: foolists
          root: "foo"
          base_level: -1
        - template: article
          folder: barriers
          root: "bar"
```

The PDF is built from each page's **file** — the Markdown the page is written
in, read through the tmark reader, never from the rendered HTML and never from
what another plugin made of the text while the site rendered. Each page is
parsed under its own path, with its metadata and the site declarations
re-emitted in front of the body and the site's `auto_append` after it, so a
diagnostic names the line you edit (`docs/syntax/tables.md:42:5`) and an asset
the page names relatively is looked up from the page's own directory. The
counters are seeded where the site's chain stood before the book's first page,
so `FW-10` is `FW-10` on both media.

Because the book reads the files, `mkdocs build` and
[`texsmith site build`](#the-book-is-a-command) write the **same bytes**: one
book path, two ways of reaching it. What the parser was handed is dropped next
to the output under `<build_dir>/<folder>/sources/` — front matter, body,
appended definitions — as a debugging artefact; nothing reads it back.

A book is not the plugin's own work: `texsmith.site.book` builds it, and the
plugin is the adapter that hands it MkDocs' navigation. The same builder runs
under [`texsmith site build`](#the-book-is-a-command), which is how a
generator with no `on_post_build` gets the same PDF.

## Serve

Under `mkdocs serve` the plugin lowers the pages and reports diagnostics but
builds no book: the PDF is a `mkdocs build` matter.

## Build

`mkdocs build` writes every book's `.tex` and its assets under `press/`. Set
`TEXSMITH_BUILD=1` to compile the PDF in the same run:

```console
$ TEXSMITH_BUILD=1 mkdocs build
```

A complete example lives in `examples/mkdocs` (`make -C examples/mkdocs` builds
the site and the PDF).

## Zensical

[Zensical](https://zensical.org) reads the same `mkdocs.yml`, but it has no
plugin hooks at all: the only thing it calls Python for is rendering Markdown.
The web lowering is therefore also a Python-Markdown extension,
`texsmith.site.web`, driving the same code as the plugin:

```yaml
markdown_extensions:
  - texsmith.site.web
extra_css:
  - assets/texsmith/texsmith.css
```

Listing the extension under MkDocs is harmless — it acts only when Zensical's
rendering context is on the `Markdown` instance, and under MkDocs the plugin
does the work through its hooks. Keep the `texsmith:` block under `plugins:`:
Zensical ignores the plugins it does not know, and the extension reads the
options from the configuration file, since Zensical drops them from its own
view of it.

Two settings have to suit both generators. `pymdownx.snippets`' `base_path`
cannot carry the `!relative` tag, which Zensical's loader does not know, so it
is a plain `base_path: .` — the directory every documented command runs from.
And `extra_css` must name the stylesheet: Zensical reads that list before
Python runs, so the extension cannot add it the way the plugin does.

### Snippets and the books

`pymdownx.snippets` renders the web; the books read the Markdown sources
directly, so TeXSmith honours two of its settings itself:

- `base_path` is where a fence's `include=`, and the deprecated `--8<--`, are
  looked up when the page's own directory does not hold them — on the web and
  in the PDF alike.
- `auto_append` names files the extension appends to every page. The books
  append them to every page's source too: a shared `includes/abbreviations.md`
  is how a site gives every page the acronym definitions, and an acronym
  reaches the PDF's glossary only through a definition in the page that uses
  it. The book's glossary carries one `\newacronym` per acronym a page
  actually writes, however many pages define it.

A site whose navigation lives in `.nav.yml` files needs one more line. Zensical
reads them only when `awesome-nav` is listed under `plugins:` — it arms its own
reader on the plugin's presence, not on the files being there — so a site that
relied on `awesome-pages` adds the newer name:

```yaml
plugins:
  - awesome-nav
```

The file's contents also differ on one point: awesome-pages' `arrange:` lists
the items it reorders and appends everything else implicitly, while awesome-nav
does not. Converting `arrange:` to `nav:` therefore ends with a `- "*"`, or the
pages the list does not name disappear from the navigation — and from a book
built out of it:

```yaml
nav:
  - intro.md
  - basics
  - "*"
```

Per page the extension does what the plugin does: the pre-pass over every page
in navigation order, and the lowering. It runs once per page — mkdocstrings
renders each docstring through a `Markdown` instance of its own, and only the
page's own instance is lowered.

### The generated files come first

What the extension cannot do is leave a file behind for the build to publish.
Zensical empties the site directory when a build starts, and it caches every
rendered page: a second build finds the cache warm, replays the HTML and never
calls Python at all. A stylesheet or a preview written while a page rendered is
therefore deleted by the next build and never written again — the page keeps
linking to a file nobody makes any more.

That cache is also why a change to the extension can look like no change at
all: `.cache/` replays a page whose source has not moved without calling Python
again, so a new TeXSmith, a new option under `texsmith:` or an edited extension
reaches the pages only once the cache is dropped:

```console
$ zensical build -c -f mkdocs.yml
```

The generated files are sources instead. `texsmith site assets` writes them
under `docs_dir`, before Zensical runs, and the build copies them like any
hand-written image:

```console
$ texsmith site assets mkdocs.yml
$ zensical build -f mkdocs.yml
```

The command reads the same configuration file the extension reads — pass a
path, or let it find `mkdocs.yml`, `mkdocs.yaml` or `zensical.toml` in the
current directory. It resolves the navigation for the order and walks **every**
Markdown page under `docs_dir` for `.snippet` fences and `.drawio` images — the
pages `exclude_docs` hides included, since Zensical publishes them anyway — and
renders each fence's preview into
`docs/assets/snippets/`, exports each diagram to `docs/assets/drawio/` as an
SVG under the diagram's own relative path, writes
`docs/assets/texsmith/texsmith.css`, and deletes from both directories what no
page asks for any more. A preview is named after the digest of its fence and a
diagram is exported through the converter's digest cache, so the second run
rebuilds nothing; an asset that will not build is reported with the name of its
page, and the others are made anyway. All three directories are generated:
keep them out of version control.

The SVG is what Zensical shows of a diagram: it has no draw.io plugin, so the
extension rewrites `<img src="x.drawio">` to the export beside it — and leaves
the tag alone, with a warning naming this command, when the export is not
there. The `.drawio` file stays where it is: MkDocs' plugin still reads it, and
the PDF export still turns it into a vector PDF.

`make docs-zensical` and `make serve-zensical` run the command first.

```console
$ zensical serve -f mkdocs.yml
```

Under `zensical serve` an edited page invalidates the pre-pass, which is redone
for the whole site; the pages Zensical does not re-render keep the numbers of
the previous build until the next one. A snippet added or edited between two
runs of `texsmith site assets` is not lost either: rendering the page writes
the missing preview under `docs_dir`, which is a directory Zensical watches, so
the file appearing there triggers the rebuild that publishes it. That rebuild
finds the cache warm and writes nothing, so it stops there.

### Index entries are the page's tags

Zensical writes `search.json` in Rust once Python is done, so nothing a page
renders can reach it — and nothing needs to. The *Filters* panel of the search
dialog lists the `tags` of the matching entries, and clicking one narrows the
results to the pages that carry it; with no query at all, it lists them. Those
tags come from a page's `tags:` metadata, which Zensical also turns into the
chips under the content and into the entries of a `<!-- material/tags -->`
listing page. Metadata is the one thing Python can still hand the build, so
that is where a page's index entries go.

`#[pointeur]` puts `pointeur` in the page's `tags`, `#[mémoire][allocation]`
puts `mémoire` and stops there — a sub-entry is the shape of a printed index,
not of a chip — and an inverted entry gives the head it files under, so
`#[Boole, George]` is the chip `Boole` and `#[Hanoï, tours de]` the chip
`Hanoï`. The tags the page declares itself come first and stay. Set `web.tags`
to `none` to leave a page's `tags:` exactly as it wrote them.

```yaml
plugins:
  - texsmith:
      web:
        tags: index # index (default) | none
```

A page that would rather not show the chips says `hide: [tags]` in its front
matter; the search filters are unaffected. And since a page's metadata is part
of its cached render, changing `web.tags` calls for `zensical build -c`.

Nothing is added to `search.json` itself. Its `tags` are a facet of exact
values, not a searchable field, and the `text` beside them is what a result's
excerpt is built from — inside a shadow root, where no stylesheet the site
ships can reach. Terms written there showed under every excerpt as a tail of
words with no relation to the match. They buy little: an index term is nearly
always in the prose of the section that declares it (on this project's own
corpus, 91% word for word), a term that is not is still typable through the
tags listing page, which is a page of the site like any other, and the few
that answer neither are *inverted* spellings nobody types.

This is Zensical only. Under MkDocs, Material's own `tags` plugin collects a
page's tags from `on_page_markdown` at the same priority as this plugin and is
declared before it, so it reads the metadata before the lowering writes it;
index entries reach MkDocs' search through the `tags` field of
`search_index.json`, which lunr indexes and Material boosts, and which the
plugin patches from `on_post_build`.

### The book is a command

A book hangs off `on_post_build` under MkDocs, a hook Zensical has not got, so
it is a command of its own — and the same builder, `texsmith.site.book`, is
behind both:

```console
$ texsmith site build mkdocs.yml
```

It reads the `books:` of the `texsmith:` block exactly as the plugin does,
resolves the navigation the way the pre-pass does, pre-passes every page so the
book's counters and cross-page references carry the numbers the site gives
them, writes the bundle under `build_dir` (`press/` by default) and compiles
the PDF, printing where it landed. `--build-dir DIR` puts the bundle elsewhere,
`--book TITLE` builds one book of several, `--no-pdf` stops at the `.tex`, and
`--strict` and `--diagnostics-json` behave as they do on the root command: the
strict check runs once the `.tex` is written and before the engine, so the
output is there to read. `mkdocs` is not imported anywhere on its path.

The `.tex` it writes is the `.tex` `TEXSMITH_BUILD=1 mkdocs build` writes, byte
for byte — the same navigation, and the same files read the same way, which is
what makes the claim hold whatever the site's other plugins do to the Markdown
on their way to the HTML. `make docs-zensical` runs it after the site.

What does not carry over yet:

- **`exclude_docs`.** Zensical builds the pages MkDocs excludes, so a file
  under `docs/` that only exists to be included somewhere else becomes a page
  of its own; nothing on the TeXSmith side can prevent that. Each is lowered
  on its own, with the numbers that follow the last page of the navigation,
  and neither the numbering of the site nor its label map is affected. Keeping
  one out of the search is Material's own front matter, which Zensical does
  honour:

  ```yaml
  ---
  search:
    exclude: true
  ---
  ```

### The versioned site is published by a script

The version selector is Material's own bundle, which Zensical ships too: it
builds itself from the `versions.json` at the root of the `gh-pages` branch as
soon as the page carries a version, which `mkdocs.yml` declares once for both
generators:

```yaml
extra:
  version:
    provider: mike
```

What `mike` cannot do is publish a site it did not build — `mike deploy` takes
a configuration file and runs MkDocs itself, with no way to be handed the
directory Zensical wrote. `scripts/publish_docs.py` takes that directory
instead and writes the branch layout `mike` wrote:

```console
$ uv run zensical build -f mkdocs.yml
$ uv run python scripts/publish_docs.py 0.8.0 --alias latest
```

The site goes under `0.8.0/`, `latest/` becomes one redirect page per page of
that version, `versions.json` gains the entry and loses the alias from its
previous holder, and the root `index.html` redirects to the alias. It checks
`origin/gh-pages` out as a git worktree under `build/gh-pages` — `--worktree
DIR` uses a checkout of yours — and stops at the commit, so a run is there to
read before anything leaves the machine. `--push` publishes it, which is what
the release workflow adds. The script needs nothing but Python.
