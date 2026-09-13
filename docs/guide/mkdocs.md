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

## Site-wide declarations

Counters declared under the plugin's `declare:` key apply to every page, as
`press.declare` does in a page's front matter:

```yaml
plugins:
  - texsmith:
      declare:
        counters:
          req:
            name: Requirement
            format: "REQ-{n:03d}"
            start: 100
```

A page may still declare its own in its front matter; the page's declaration
wins over the site's for the same prefix. See
[Counters](../syntax/counters.md) for the numbering rules.

## Options

| Option | Description | Default |
| --- | --- | --- |
| `enabled` | Turn the plugin off entirely | `true` |
| `template` | Template used for the books | `book` |
| `build_dir` | Where the `.tex`, the assets and the PDF land | `press` |
| `declare` | Site-wide declarations (`declare.counters`) | `{}` |
| `web` | `tmark.lower_web` options: `sections` (`title` \| `number`), `citations` (`inline` \| `passthrough`), `css_prefix` | `{}` |
| `inject_markdown_extensions` | Enable the extensions the lowering relies on | `true` |
| `css` | Ship and register `texsmith.css` | `true` |
| `language` | Document language, else the theme's | *theme* |
| `bibliography` | `.bib` files shared by every book | `[]` |
| `books` | The documents to export (below) | `[]` |
| `template_overrides` | Template attributes for every book | `{}` |
| `copy_assets` / `clean_assets` | Copy the referenced assets / prune the unused ones | `true` |
| `save_html` | Keep a snapshot of each page's rendered HTML | `false` |
| `embed_fragments` | Inline the page fragments instead of `\input` | `false` |

## Books

A book is one PDF built from a section of the navigation. Several may be
declared; `root: "__texsmith_full_navigation__"` takes the whole site.

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

The PDF is built from each page's **source** — the Markdown MkDocs handed the
plugin, macros expanded, with the page metadata and the site declarations back
in front of it — read through the tmark reader, not from the rendered HTML. The
exact input is written next to the output under `<build_dir>/<folder>/sources/`,
so what the PDF was built from is always inspectable. The counters are seeded
where the site's chain stood before the book's first page, so `FW-10` is
`FW-10` on both media.

A page whose front matter says `press: {reader: html}` is read from its
rendered HTML instead — the escape hatch for a page whose content is produced
by another MkDocs plugin.

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
