# Custom counters

Technical documents number things that LaTeX knows nothing about: findings,
requirements, bugs, risks, test cases. Declare such a series under
`press.declare.counters`, define each item in the body, and refer to it with
the ordinary `@` sigil — the numbers are computed by TeXSmith rather than by
the backend, so the LaTeX build, the Typst build and the MkDocs site all show
the same values.

```md
---
press:
  declare:
    counters:
      n: {name: Requirement, format: "N-{n:02d}"}
---

| Id | Requirement |
| --- | --- |
| {counter}(n:joy) | Everyone shall be happy |
| {counter}(n:respect) | Everyone shall respect the others |

Smile in every circumstance (@n:joy) and do no harm to others (@n:respect).
```

renders as

| Id | Requirement |
| --- | --- |
| N-01 | Everyone shall be happy |
| N-02 | Everyone shall respect the others |

Smile in every circumstance (N-01) and do no harm to others (N-02).

Both `N-01` occurrences are the same PDF anchor: the table cell is the target,
the parenthesised one is a clickable link.

## One registry for every series

Every referenceable series is an entry of the **counter registry**, keyed by
its prefix. The built-in prefixes are simply predeclared entries; there is no
second mechanism for "reserved prefixes".

| Prefix | Name | Scope | Numbered by | Applies to |
| ------ | ---- | ----- | ----------- | ---------- |
| `part` `chap` `sec` `app` | Part, Chapter, Section, Appendix | document | backend | headings |
| `fig` | Figure | chapter | backend | images, sub-figures |
| `tbl` | Table | chapter | backend | tables |
| `lst` | Listing | chapter | backend | code blocks |
| `eq` | Equation | chapter | backend | display math |
| `thm` | Theorem | chapter | backend | theorem-type callouts |
| `note` | Note | document | backend | footnotes |
| `gls` | — | — | — | [glossary entries](notes.md#glossary) |
| `doi` | — | — | — | [DOIs cited in place](references.md#bibliographic-references) |

A user-declared entry adds a series the backend knows nothing about:

```yaml
press:
  declare:
    counters:
      fw: {name: Finding, format: "FW-{n:02d}", start: 1, scope: document}
```

`name`
:   The label word, used in references and diagnostics.

`format`
:   A Python format string over the fields `n` (the value), `prefix` and
    `key`; it defaults to `"{n}"`, so `"FW-{n:02d}"` pads to two digits. An
    invalid format (`{oops}`, unbalanced braces) is an error at parse time.

`start`
:   The first value; defaults to 1.

`scope`
:   `document | chapter | section`. It is a **hint** to whoever numbers the
    series: under site-wide numbering every series is `document` and
    continuous, so the same document may print "Figure 3.2" and show
    "Figure 12".

`ref`
:   The template a reference renders, with the fields `{name}` and `{number}`.
    It defaults to `"{number}"` when a `format` is given — a formatted number
    such as `FW-01` is self-identifying — and to `"{name} {number}"` otherwise,
    which is what the predeclared entries use.

A prefix matches `[A-Za-z][A-Za-z0-9_-]*` and is matched case-insensitively, so
`@Fw:boot-loop` capitalises the label word at the start of a sentence. You may
override the fields of a predeclared entry (`fig: {scope: document}`) but not
add a prefix that shadows a role name.

!!! note "`declare:` may sit at the root"
    `press` is an optional namespace: every key TMark reads may sit at the root
    of the front matter or under `press:`, and `press` wins when both are
    present. The namespace exists so that a file shared with a static site
    generator keeps the root free. A top-level `counters:` key is the 0.6
    spelling, accepted with a deprecation warning; `tmark lint --fix` moves it
    under `press.declare`. See [Migrating to TMark](../guide/migration.md).

## Defining an item

### `{counter}(prefix:key)` — define and print

The canonical form is a role, and its key is an **argument**, hence the
parentheses: nothing inside them is Markdown.

```md
---
press:
  declare:
    counters:
      fw: {name: Finding, format: "FW-{n:02d}"}
---

{counter}(fw:boot-loop) The firmware reboots when the watchdog fires.
```

It is a plain inline construct: it works in a paragraph, a table cell, a list
item, a callout title, a heading. Numbers are allocated in document order.

*Shorthand:* `#(fw:boot-loop)` — the `#` sigil with the same argument
bracketing, one character shorter and the same node. `\#` forces a literal
`#`, and nothing is ever substituted inside a code span or a fenced block.

!!! note "`#{prefix:key}` is deprecated"
    The 0.6 marker is still recognised, and only when its prefix is
    **declared** — so a Ruby or CoffeeScript interpolation such as
    `#{user.name}` in prose stays the literal text it is. `tmark lint --fix`
    rewrites it to `#(prefix:key)`.

### `{#prefix:key}` — define silently

Any element carrying an id whose prefix is declared is numbered too, without
printing anything. This is the ordinary [attribute](extra.md) syntax, so it
attaches to headings, figures and tables:

```md
---
press:
  declare:
    counters:
      fw: {name: Finding, format: "FW-{n:02d}"}
---

## Boot loop {#fw:boot-loop}

![Watchdog trace](trace.png){#fw:trace}

The watchdog issue (@fw:boot-loop) is fixed in 1.4.2.
```

`@fw:boot-loop` resolves to `FW-01` even though the number appears nowhere in
the heading.

!!! warning "An attribute needs a host"
    An attribute list is consumed at the end of a heading, on an image, or on a
    line of its own after a block. In the middle of a sentence, or in a table
    cell, it has nothing to attach to — that is exactly the case
    `{counter}(…)` exists for.

## Referring to an item

`@prefix:key`, or `@[prefix:key]` when the reference contains a space. This is
the regular [reference sigil](references.md); a declared prefix simply routes
it to the counter registry.

```md
---
press:
  declare:
    counters:
      fw: {name: Finding, format: "FW-{n:02d}"}
---

{counter}(fw:boot-loop) The firmware reboots.

The watchdog issue (@fw:boot-loop) is fixed in 1.4.2.
```

The reference renders the `ref` template. With a `format` declared that
defaults to the number alone — `FW-01`, not `Finding FW-01` — so write the noun
yourself, as you would for a section, or declare `ref: "{name} {number}"`.

## Diagnostics

| Situation | Code |
| --- | --- |
| `@n:missing` — no such item | `ref-unresolved`, and a visible `[?n:missing]` |
| the same key defined twice | `label-duplicate` |
| `{counter}(x:joy)` with `x` undeclared | `prefix-unknown` |
| `{#tbl:x}` on a figure | `prefix-host-mismatch` |
| an invalid `format` or prefix | an error at parse time |

## Scope and stability

Numbers are allocated in document order and shared across all the documents of
a multi-document build — `a.md`, `b.md` and `c.md` continue a single series
rather than restarting.

!!! danger "Numbers are positional"
    Inserting an item renumbers every item after it. When the identifiers leave
    the document — a finding quoted in an audit report, a requirement cited in a
    test plan — that renumbering breaks the external traceability silently.
    Pin the values with a dedicated `start:` per counter and stable ordering, or
    keep the volatile numbering for internal documents only. Explicit pinning is
    planned but not implemented yet.

## Backend mapping

| | Definition | Reference |
| --- | --- | --- |
| LaTeX | `\phantomsection\label{n:joy}N-01` | `\hyperref[n:joy]{N-01}` |
| Typst | `N-01<n:joy>` | `#link(<n:joy>)[N-01]` |
| HTML | `<span class="ts-counter" data-counter="n" data-key="joy" id="n:joy">N-01</span>` | `<a href="#n:joy">N-01</a>` |

`\phantomsection` is what makes the `hyperref` anchor land on the item rather
than on the enclosing section, and it lets `\pageref{n:joy}` work.

## On a MkDocs site

The [`texsmith` MkDocs plugin](../guide/mkdocs.md) (package `mkdocs_texsmith`)
renders counters on the site. One plugin, no Markdown extension to wire:

```yaml
plugins:
  - texsmith:
      declare:
        counters: # optional site-wide declarations
          req:
            name: Requirement
            format: "REQ-{n:03d}"
            start: 100
```

!!! warning "`texsmith.counters` and `texsmith.index` are gone"
    Those two standalone plugins are the 0.6 spelling. They still load — each
    logs a deprecation warning and does nothing — but no longer number
    anything; the single `texsmith` plugin above does both jobs (counters and
    search-index entries) site-wide. Remove them from `plugins:` in
    `mkdocs.yml` and move any `counters:` they declared under
    `declare.counters`. The entry points disappear in 0.8.

Counters declared under `declare.counters` apply to the whole site; a page may
declare its own under `press.declare.counters` in its front matter, and the
page's declaration wins for the same prefix. Every *item* is visible from every
page — a series defined in `findings.md` is referenceable from `index.md`.

Numbering is **site-wide, in navigation order**: a pre-pass parses and resolves
every page before any of them is converted, chaining each page's counters after
the previous page's, so a reference on the first page resolves to an item
defined on the last one. Cross-page references are rewritten to point at the
page that defines the item (`<a href="findings/#fw:watchdog">FW-01</a>`);
same-page ones keep a local anchor (`<a href="#fw:watchdog">FW-01</a>`).

The pre-pass parses the page rather than scanning it, so a marker inside a
fence or a code span is never counted, and `#{user.name}` in prose stays the
literal text it is.

A user-declared series such as `fw:` above is always numbered by tmark itself
— no backend knows about it, on the site or in a standalone build. This
differs from the *predeclared* series of the [registry](#one-registry-for-every-series)
(`fig`, `tbl`, `lst`, `eq`, `sec`, …): a standalone `texsmith` build lets LaTeX
or Typst allocate those (`--numbering backend`, the CLI default) or has tmark
allocate them instead so both backends agree (`--numbering tmark`). The MkDocs
plugin always resolves every page with tmark numbering every series —
equivalent to `--numbering tmark` — because a number allocated by the LaTeX or
Typst backend of one page would mean nothing site-wide.

## Citing an item from another document

A number allocated here means nothing in a sister document, and a renumbering
breaks every hard-coded `FW-10` it contains. Publish an inventory and cite it
explicitly — see [Cross-document references](crossrefs.md).

## Not implemented yet

Auto-generated listings (a "List of requirements" table), extra per-item
attributes (status, priority, source), back-references ("cited on pages 4,
12"), hierarchical numbering (`FW-3.2`) and per-chapter resets are deliberately
out of the first iteration.
