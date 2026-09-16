#set document(
title: "Integration with MkDocs",
)
#set page(
paper: "a4",
margin: 2.5cm,
numbering: none,
footer: context {
if counter(page).final().first() > 1 {
align(center)[#counter(page).get().first()]
}
},
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
#text(size: 1.8em, weight: "bold")[Integration with MkDocs]]
#v(1.5em)

#ts-callout-style.update("fancy")

One plugin, `texsmith`, carries the whole integration: it renders the TMark
constructs on the site _and_ exports the same sources as a PDF. Add it to
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

#ts-callout(kind: "warning", title: [The `texsmith.counters` and `texsmith.index` plugins are gone])[
Both jobs belong to `texsmith` now. The two entry points still load, log a
warning and do nothing; they disappear in 0.8. Remove them from `plugins:`
and move any `counters:` you declared under them to `declare.counters`
(below).]

= What the plugin does to a page

Before Python-Markdown runs, every page goes through `tmark`:

+ a *pre-pass* parses and resolves every page in navigation order, chaining
the counters from one page to the next, and collects the labels of the whole
site;
+ each page is then resolved again against that site map and *lowered*: each
TMark construct is replaced by the Markdown or HTML Material renders — a
callout becomes an admonition, a figure a `<figure>`, a counter item a
`<span class="ts-counter">` — and every other byte is left alone.

So Material's own syntax (`++ctrl+alt+del++`, `==marked==`, tab sets, emoji,
mermaid fences, an `mkdocstrings` block) passes through untouched, and a
construct TeXSmith owns renders the same way it does in the PDF.

Diagnostics are reported with the page path: `docs/findings.md:12:5: warning
ref-unresolved: …`.

= Site-wide declarations

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
See Counters for the numbering rules.

Both reach the *parser*, not only the renderer, so a callout kind declared
here is one `::: exercise` can be spelled with anywhere on the site — on the
web and in the books alike. A kind nothing declares is `container-unknown`
and its fence stays literal text on the page.

= Options

#table(
columns: 3,
align: (left, left, left),
table.header([Option], [Description], [Default]),
[`enabled`], [Turn the plugin off entirely], [`true`],
[`template`], [Template used for the books], [`book`],
[`build_dir`], [Where the `.tex`, the assets and the PDF land], [`press`],
[`declare`], [Site-wide declarations (`declare.counters`, `declare.admonitions`, `declare.glossary`)], [`{}`],
[`web`], [`tmark.lower_web` options: `sections` (`title` | `number`), `citations` (`inline` | `passthrough`), `css_prefix`], [`{}`],
[`inject_markdown_extensions`], [Enable the extensions the lowering relies on], [`true`],
[`css`], [Ship and register `texsmith.css`], [`true`],
[`language`], [Document language, else the theme's], [_theme_],
[`bibliography`], [`.bib` files shared by every book], [`[]`],
[`books`], [The documents to export (below)], [`[]`],
[`template_overrides`], [Template attributes for every book], [`{}`],
[`copy_assets` / `clean_assets`], [Copy the referenced assets / prune the unused ones], [`true`],
[`embed_documents`], [Inline each page's body instead of `\input`], [`false`],
)

= Books

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

The PDF is built from each page's *source* — the Markdown MkDocs handed the
plugin, macros expanded, with the page metadata and the site declarations back
in front of it — read through the tmark reader, not from the rendered HTML. The
exact input is written next to the output under `<build_dir>/<folder>/sources/`,
so what the PDF was built from is always inspectable. The counters are seeded
where the site's chain stood before the book's first page, so `FW-10` is
`FW-10` on both media.

A book is not the plugin's own work: `texsmith.site.book` builds it, and the
plugin is the adapter that hands it MkDocs' navigation. The same builder runs
under #link(<the-book-is-a-command>)[`texsmith site build`], which is how a
generator with no `on_post_build` gets the same PDF.

= Serve

Under `mkdocs serve` the plugin lowers the pages and reports diagnostics but
builds no book: the PDF is a `mkdocs build` matter.

= Build

`mkdocs build` writes every book's `.tex` and its assets under `press/`. Set
`TEXSMITH_BUILD=1` to compile the PDF in the same run:

```console
$ TEXSMITH_BUILD=1 mkdocs build
```

A complete example lives in `examples/mkdocs` (`make -C examples/mkdocs` builds
the site and the PDF).

= Zensical

#link("https://zensical.org")[Zensical] reads the same `mkdocs.yml`, but it has no
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

== The generated files come first

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
current directory. It resolves the navigation, walks every page for `.snippet`
fences and `.drawio` images, renders each fence's preview into
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

== The search index comes last

Zensical writes `search.json` in Rust once Python is done, so nothing a page
renders can reach it. The index entries a page declares (`#[term]`) are put
there afterwards, by a second command:

```console
$ zensical build -f mkdocs.yml
$ texsmith site search mkdocs.yml
```

It walks the built site for the `ts-index` markers the lowering left in the
pages, keys them by page and by section heading the way the index does, and
adds them to the entries that match. Both index formats are understood: the
`tags` field of MkDocs' `search/search_index.json`, which Material searches and
boosts, and the `text` of Zensical's `search.json` — the field its query reads,
since `tags` there are the filter chips, an aggregation of exact values rather
than something a reader types. `make docs-zensical` runs the command after the
build.

== The book is a command <the-book-is-a-command>

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
the PDF, printing where it landed. `–build-dir DIR` puts the bundle elsewhere,
`–book TITLE` builds one book of several, `–no-pdf` stops at the `.tex`, and
`–strict` and `–diagnostics-json` behave as they do on the root command: the
strict check runs once the `.tex` is written and before the engine, so the
output is there to read. `mkdocs` is not imported anywhere on its path.

The `.tex` it writes is the `.tex` `TEXSMITH_BUILD=1 mkdocs build` writes, byte
for byte. `make docs-zensical` runs it after the site.

What does not carry over yet:

- *`mike`.* Versioning is not supported: there is no version selector.
- *`exclude_docs`.* Zensical builds the pages MkDocs excludes, so a file
under `docs/` that only exists to be included somewhere else becomes a page
of its own; nothing on the TeXSmith side can prevent that. They are lowered
like any other page, after the ones the navigation reaches, and the numbering
of the site is unaffected.
