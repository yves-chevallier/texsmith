#set document(
title: "Migrating to TMark",
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
#text(size: 1.8em, weight: "bold")[Migrating to TMark]]
#v(1.5em)

#ts-callout-style.update("fancy")

TeXSmith 0.7 parses its Markdown with #link("https://github.com/yves-chevallier/tmark")[TMark],
a CommonMark parser with a specified extension set, instead of Python-Markdown
and its plugin stack. Every spelling TeXSmith 0.6 understood is still accepted,
but most of them are now _deprecated sugar_: the parser warns, and the
canonical spelling is what the documentation teaches and what the printer
emits.

Nothing in your corpus breaks on the day you upgrade. This page tells you what
to change, how to change it in one command, and which behaviours differ because
the parser changed.

= One command

`tmark lint` reports every deprecated spelling with its replacement, and
`–fix` rewrites them:

```bash
tmark lint report.md              # list what would change
tmark lint --fix --diff report.md # preview the rewrite as a unified diff
tmark lint --fix --stdout report.md > fixed.md
tmark lint --fix report.md        # rewrite the file in place
```

`–fix` only applies the _safe_ fixes — the mechanical one-to-one rewrites of
the table below. Without `–stdout` or `–diff` the files are rewritten in
place, so run it on a clean working tree.

A whole tree at once:

```bash
tmark lint --fix docs/**/*.md
```

Run `tmark lint –strict` afterwards: what remains is either a genuine
diagnostic or one of the sugars kept indefinitely.

= What changes

Every row is accepted today. "fmt" in the _Horizon_ column means the spelling
is scheduled for removal once `tmark fmt` has shipped long enough to have
rewritten the corpus; "indefinite" means it is part of the dialect's
compatibility promise and is not going away — usually because MkDocs Material
or Pandoc renders it natively.

== Inline constructs

#table(
columns: (1fr, 1fr, 1fr),
align: (left, left, left),
table.header([Legacy], [Canonical], [Horizon]),
[`[^key]` citation], [`@key`], [fmt; `[^1]` stays a _footnote_; meaning-preserving — both are the short, parenthetical citation, and `–fix` inserts a space when the `[^key]` hugs the word before it],
[`^[k1,k2]` citation], [`@[k1; k2]`], [fmt; `^[…]` then becomes an inline footnote; same meaning-preserving rewrite, with the same hugging-space fix],
[`[@key, p. 3]` (Pandoc)], [`@[key, p. 3]`], [indefinite (Pandoc import)],
[`@https://doi.org/10.…`], [`@doi:10.…`], [indefinite (sugar)],
[`[](gls:term)`], [`@gls:term`], [fmt],
[`{latex}[\clearpage]`], [`{raw latex}(\clearpage)`], [fmt],
[`{typst}[…]`, `{html}[…]`], [`{raw typst}(…)`, `{raw html}(…)`], [fmt],
[`{margin}[…]`], [`{aside}[…]`], [fmt],
[`{margin}[…]{l}` / `{r}` / `{o}` / `{i}`], [`{aside side=left}[…]` / `right` / `outer` / `inner`], [fmt],
[`#{prefix:key}` counter marker], [`#(prefix:key)`], [fmt],
[`{index:registry}[…]`], [`{index registry=…}[…]`], [fmt],
[`{index}[…]{b}`], [`{index main=true}[…]`], [fmt],
[`{index}[…]{i}`], [content markup: `{index}[*term*]`], [fmt],
[`{: .thin #id}` attribute list], [`{.thin #id}`], [fmt],
[`[=9/20 "Review"]`], [`[=45% "Review"]`], [fmt],
)

== Blocks

#table(
columns: (1fr, 1fr, 1fr),
align: (left, left, left),
table.header([Legacy], [Canonical], [Horizon]),
[`/// latex … ///`], [a ```` ```latex raw ```` fence], [fmt],
[`latex render` fence (draft 2)], [```` ```latex raw ````], [never shipped],
[`/// caption` with an indented `attrs:` line], [a `Figure:` / `Table:` / `Listing:` caption line], [fmt],
[`/// figure-caption`], [`Figure: … {#fig:x}`], [fmt],
[`–8<– "file"`], [`{include}(file)`], [fmt],
[`::: margin`], [`::: aside`], [fmt],
[`Table:` line _before_ the table], [`Table:` line _after_ the table], [indefinite (Pandoc accepts both)],
[`!!! note` / `??? note` callouts], [`::: note {title="…" collapsed=true}`], [indefinite (Material renders them)],
[`=== "Windows"` content tabs], [`::: tabs` + `::: tab {title=Windows}`], [indefinite (Material renders them)],
[`<div markdown>`], [`::: div`], [indefinite (the only container a Python-Markdown site renders)],
[bare ```` ```mermaid ```` fence], [```` ```mermaid image ````], [indefinite (MkDocs renders it)],
)

== Front matter

#table(
columns: (1fr, 1fr, 1fr),
align: (left, left, left),
table.header([Legacy], [Canonical], [Horizon]),
[top-level `bibliography:`], [`press.sources.bibliography`], [fmt],
[top-level `crossrefs:`], [`press.sources.crossrefs`], [fmt],
[top-level `counters:`], [`press.declare.counters`], [fmt],
[top-level `glossary:`], [`press.declare.glossary`], [fmt],
[top-level `acronyms:`], [`press.declare.acronyms`], [fmt],
[top-level `admonitions:`], [`press.declare.admonitions`], [fmt],
[`admonitions.<type>.icon` / `.color`], [`press.callouts.<type>`], [fmt],
[`press.callout_style`, `press.admonition_style`], [`press.callouts.style`], [fmt],
[`–no-promote-title`], [`title: null`], [indefinite],
)

`title`, `authors`, `date`, `lang` and `id` stay at the *root* of the front
matter: that is where MkDocs, Pandoc and editors read them. Only the keys
TeXSmith owns move under `press:`, and even those may still sit at the root —
`press` is a namespace that keeps them out of a static-site generator's way,
not a requirement.

Before:

```yaml
---
title: Revue firmware
counters:
  fw: {name: Constat, format: "FW-{n:02d}"}
bibliography:
  ein05: https://doi.org/10.1002/andp.19053221004
crossrefs:
  fwrev: build/firmware-review.refs.json
press:
  callout_style: classic
---
```

After:

```yaml
---
title: Revue firmware
press:
  callouts:
    style: classic
  declare:
    counters:
      fw: {name: Constat, format: "FW-{n:02d}"}
  sources:
    bibliography:
      ein05: https://doi.org/10.1002/andp.19053221004
    crossrefs:
      fwrev: build/firmware-review.refs.json
---
```

== MkDocs plugin options

#table(
columns: (1fr, 1fr, 1fr),
align: (left, left, left),
table.header([Legacy], [Canonical], [Horizon]),
[`save_html: true`], [—], [removed in 0.7],
)

`save_html` saved the rendered HTML of every page next to the book. Nothing
reads it any more: since the TMark migration the PDF is built from each page's
Markdown, so the snapshot recorded a document the book did not come from. The
option is gone rather than ignored, and MkDocs says so — `Plugin 'texsmith'
option 'save_html': Unrecognised configuration name` — so a configuration that
still carries it is told, and the build carries on.

What the book _was_ built from is written unconditionally: one
`<build_dir>/<folder>/sources/**.md` per page, the page's Markdown with its
metadata and the site's declarations back in front of it, exactly what the
reader parsed. That is the file to read when a PDF and a page disagree.

= Behaviour changes that are not bugs

These are not deprecations: they are places where a CommonMark parser reads
your bytes differently from Python-Markdown. `tmark lint –fix` cannot repair
them, because in each case the _old_ reading was the accident.

/ Lazy continuation lines: CommonMark continues a paragraph inside a block quote or a list item even
when the continuation line carries no marker. A line following `> quote`
with no `>` joins the quote instead of starting a new paragraph. Put a
blank line where you meant a break.
/ List indentation: A nested list item must be indented to the _content column_ of its parent
(three spaces after `1. `, two after `- `), not by an arbitrary four. Lists
indented by four spaces under a `- ` parent become indented code blocks.
Conversely, a continuation paragraph inside a list item needs the content
column too.
/ `_` inside words: CommonMark never opens emphasis inside a word, so `snake_case_name` and
`file_name_here` stay literal. Python-Markdown's `betterem` did the same,
but the plain `markdown` behaviour did not: documents that relied on
`a_b_c` rendering as emphasis now show the underscores.
/ HTML blocks: CommonMark's seven HTML-block kinds decide where an HTML block ends. Raw
HTML is kept as typed and dropped by the paged writers. A `<div>` whose
body must be parsed as Markdown needs the `markdown` attribute, and the
canonical spelling is `::: div` anyway.
/ Entity handling: Named and numeric HTML entities (`&nbsp;`, `&#x2014;`) are decoded to the
character they name, in every backend. An ampersand that is not an entity
stays an ampersand; write `&amp;` when you mean the character in HTML
output.
/ Attribute lists need a host: `{#id .class}` attaches to the element _immediately_ before it (or to the
heading it terminates). A brace group with nothing to attach to is literal
text and raises `attributes-no-host`. Where you want attributes on a piece
of running text, wrap it in an anonymous span: `[this claim]{#claim:one}`.
The Python-Markdown spelling `{: …}` is accepted and deprecated.
/ `\@` and `\#` escapes: `@` before a word and `#` before `[` or `(` are now sigils. They are
guarded — `@` never fires inside an e-mail address, a URL, a word or code,
and `#[` or `#(` followed by a non-space does not occur in prose — but
where you do need the literal character, escape it: `\@`, `\#`.

Two further deviations from GFM are deliberate and long-standing in TeXSmith:
`__text__` is small caps, not a second bold, and `—` on its own line is a
divider that the paged templates render as a page break. Both are disabled by
the `strict` profile.

= A migration session

```bash
# 1. See what the corpus looks like today.
tmark lint docs/**/*.md 2>&1 | tee /tmp/before.txt

# 2. Preview the mechanical rewrites.
tmark lint --fix --diff docs/**/*.md | less

# 3. Apply them on a clean tree, then review the diff.
tmark lint --fix docs/**/*.md
git diff

# 4. What remains needs a human: read it with --strict.
tmark lint --strict docs/**/*.md
```

Then rebuild the documents and compare the PDFs. The constructs most likely to
move are the ones the CommonMark rules above touch — nested lists and block
quotes — not the ones `–fix` rewrote.

See also Diagnostics for the diagnostic codes and how to
promote a warning to a hard failure.
