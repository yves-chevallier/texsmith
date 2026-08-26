# Custom counters

Technical documents number things that LaTeX knows nothing about: findings,
requirements, bugs, risks, test cases. TeXSmith lets you declare such a series
in the front matter, mark each item in the body, and reference it anywhere —
the numbers are computed by TeXSmith rather than by the backend, so the LaTeX
build, the Typst build and — with the companion plugin — the MkDocs site all
show the same values.

```markdown
---
counters:
  n:
    name: Requirement
    format: "N-{n:02d}"
---

| Id | Requirement |
| --- | --- |
| #{n:joy} | Everyone shall be happy |
| #{n:respect} | Everyone shall respect the others |

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

## Declaring a counter

Each key under `counters:` is the **prefix** used by the markers.

```yaml
counters:
  n:
    name: Requirement       # human-readable name, used in diagnostics
    format: "N-{n:02d}"     # optional, defaults to "{n}"
    start: 1                # optional, defaults to 1
```

`format` is a Python format string. Three fields are available:

| Field | Meaning |
| --- | --- |
| `n` | the counter value (`1`, `2`, …), so `{n:02d}` pads it |
| `prefix` | the counter prefix (`n`) |
| `key` | the item key (`joy`) |

The format string is validated when the document is parsed; an invalid one
(`{oops}`, unbalanced braces) raises a `CounterValidationError`.

Unlike `glossary:`, a counter has no string shorthand: each entry is a mapping,
because a series without a `format` is rarely what you want.

A prefix must match `[A-Za-z][A-Za-z0-9_-]*` and must not shadow one of the
conventional built-in prefixes — `sec`, `fig`, `tbl`, `eq`, `lst`, `app`,
`chap`, `part`, `note` — which stay reserved for regular labels.

## Marking an item

### `#{prefix:key}` — define and print

The marker prints the formatted number and becomes the reference target.

```markdown
#{fw:boot-loop} The firmware reboots when the watchdog fires.
```

It is a plain inline construct: it works in a paragraph, a table cell, a list
item, an admonition title, a heading. Numbers are allocated in document order.

The marker is inert unless its prefix is declared: `#{name}` (no colon),
`#{sh:var}` with `sh` undeclared, or `#{n:joy}` in a document without a
`counters:` section all stay literal text. This keeps Ruby/CoffeeScript
interpolations (`#{user.name}`) intact. Inside code spans and fenced blocks
nothing is ever substituted, and `\#{n:joy}` forces a literal.

### `{#prefix:key}` — define silently

Any element carrying an `id` whose prefix is declared is numbered too, without
printing anything. This is the usual `attr_list` syntax, so it attaches to
headings, figures and tables:

```markdown
## Boot loop {#fw:boot-loop}

![Watchdog trace](trace.png){#fw:trace}
```

`@fw:boot-loop` then resolves to `FW-01` even though the number appears nowhere
in the heading.

!!! warning "Position matters for `{#…}`"
    `attr_list` consumes `{#…}` at the end of a heading, on an image, or on a
    line of its own after a block. In the middle of a sentence it stays literal
    text — use `#{…}` there.

## Referencing an item

`@prefix:key` (or `@[prefix:key]`) prints the formatted number as a hyperlink.
This is the regular [cross-reference shorthand](references.md); a declared
prefix simply routes it to the counter registry.

```markdown
The watchdog issue (@fw:boot-loop) is fixed in 1.4.2.
```

The reference prints the number alone — `FW-01`, not `Finding FW-01`. Write the
noun yourself, as you would for a section. The `name:` field is only used in
diagnostics.

## Diagnostics

| Situation | Behaviour |
| --- | --- |
| `@n:missing` — no such item | warning, the reference renders empty |
| `#{n:joy}` twice with the same key | warning, both print the first number |
| `#{x:joy}` — undeclared prefix | left as literal text, no warning |
| invalid `format` or prefix | `CounterValidationError` at parse time |

## Scope and stability

Numbers are allocated per conversion, in document order, and shared across all
the documents of a multi-document build — `a.md`, `b.md` and `c.md` continue a
single series rather than restarting.

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

A MkDocs build never goes through TeXSmith's front-matter parsing, so counters
need their companion plugin to render on the site:

```yaml
plugins:
  - texsmith.counters:
      counters: # optional site-wide declarations
        req:
          name: Requirement
          format: "REQ-{n:03d}"
          start: 100
```

The plugin enables the `texsmith.extensions.counters` and
`texsmith.extensions.references` Markdown extensions on its own (set
`inject_markdown_extension: false` / `inject_reference_extension: false` to wire
them by hand). Counters declared under the plugin's `counters:` key apply to the
whole site; a page may declare its own in its front matter, and every
declaration is visible from every page — a series defined in `findings.md` is
referenceable from `index.md`.

Numbering is **site-wide, in navigation order**: a pre-pass walks the nav before
any page is converted and reserves a value for every marker, so a reference on
the first page resolves to an item defined on the last one. Cross-page
references are rewritten to point at the page that defines the item
(`<a href="findings/#fw:watchdog">FW-01</a>`); same-page ones keep a local
anchor.

!!! warning "The pre-pass reads the raw Markdown"
    It strips fenced blocks and inline code spans, then scans what remains. A
    marker of a *declared* prefix written as an example in plain prose — rather
    than in a code span — is counted by the pre-pass, and consumes a number.

## Citing an item from another document

A number allocated here means nothing in a sister document, and a renumbering
breaks every hard-coded `FW-10` it contains. Publish an inventory and cite it
explicitly — see [Cross-document references](crossrefs.md).

## Not implemented yet

Auto-generated listings (a "List of requirements" table), extra per-item
attributes (status, priority, source), back-references ("cited on pages 4,
12"), hierarchical numbering (`FW-3.2`) and per-chapter resets are deliberately
out of the first iteration.

