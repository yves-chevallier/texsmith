#set document(
title: "Admonitions",
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
#text(size: 1.8em, weight: "bold")[Admonitions]]
#v(1.5em)

Admonitions — callouts — are little blocks for surfacing notes, warnings, tips,
and whatever else you need to highlight. In TMark they are *containers*, and
the canonical spelling is the `:::` fence:

```md
::: note {title="This is a Note"}
Any number of other Markdown elements.

This is the second paragraph.
:::
```

#ts-callout(kind: "note", title: [This is a Note])[
Any number of other indented Markdown elements.

This is the second paragraph.]

Folding is an attribute, not a second fence family:

```md
::: note {title="This is a Note" collapsed=true}
Any number of other Markdown elements.

This is the second paragraph.
:::
```

#ts-callout(kind: "note", title: [This is a Note], collapsed: true)[
Any number of other indented markdown elements.

This is the second paragraph.]

#ts-callout(kind: "info", title: [The PyMdownX spellings are kept indefinitely])[
`!!! note "Title"` and `??? note "Title"` (collapsed) / `???+` (expanded)
remain accepted sugar for callouts, because MkDocs Material renders them
natively. They are one node whatever the spelling. Use whichever suits the
document; `:::` is what the printer emits.]

Print has no folding, so the strategy is declared once:

```yaml
press:
  details: expand      # expand (default) | reference
```

`reference` moves the body of a collapsed callout to a grouped end-section
(“Solutions”, “Warnings”, …) and leaves a “See page N” link in its place.

= #ts-logo("LaTeX") Rendering

TeXSmith maps callouts onto the `tcolorbox` package through the `ts-callouts`
fragment, which provides the `tscallout` environment:

```latex
\begin{tscallout}[kind=note, title={This is a Note}]
…
\end{tscallout}
```

Template authors restyle them by redefining that environment or by appending to
its `pgfkeys` family. Set the global look with `press.callouts.style` (or via
`–attribute press.callouts.style=<style>`):

```yaml
---
press:
  callouts:
    style: classic  # fancy | classic | minimal
---
```

- `fancy` (default): colored headings with icons.
- `classic`: black-and-white layout with a bold left rule.
- `minimal`: subtle border, rounded corners, and no icons.

`press.callout_style` and `press.admonition_style` are the deprecated names of
that key.

#ts-div("tab", title: "Fancy Admonitions")[
#figure(
image("snippet-<HASH>.png", width: 70%),
caption: [Demo],
)]

#ts-div("tab", title: "Classic Admonitions")[
#figure(
image("snippet-<HASH>.png", width: 70%),
caption: [Demo],
)]

#ts-div("tab", title: "Minimal Admonitions")[
#figure(
image("snippet-<HASH>.png", width: 70%),
caption: [Demo],
)]

= Custom types

A new _kind_ of callout is a declaration, not a new container name. Declare what
it *is* under `press.declare`, and how it *looks* under `press.callouts`:

```yaml
press:
  declare:
    admonitions:
      solution:
        name: Solution
        group: Solutions                          # section title under `reference`
        reference: "See page {page} for the solution"
  callouts:
    solution: {icon: "🎓", color: "#123456"}      # quote it: a bare # starts a YAML comment
```

```md
---
press:
  declare:
    admonitions:
      solution: {name: Solution, group: Solutions}
---

::: solution {title="Exercise 3"}
Apply the chain rule twice.
:::
```

Theorem environments are exactly this, with a counter attached — see
#link("notes.md#theorems")[Theorems].

= Built-in Admonition Types

The following types are built in:

#ts-callout(kind: "note")[
A Note]

#ts-callout(kind: "tip")[
A Tip]

#ts-callout(kind: "warning")[
A Warning]

#ts-callout(kind: "important")[
An important notice]

#ts-callout(kind: "danger")[
A danger notice]

#ts-callout(kind: "info")[
An info notice]

#ts-callout(kind: "hint")[
A Hint]

#ts-callout(kind: "seealso")[
A see-also notice]

#ts-callout(kind: "question")[
A question notice]

#ts-callout(kind: "abstract")[
An abstract]

= Content tabs

A `tabs` container holds `tab` containers, each with a `title=`:

```md
:::: tabs
::: tab {title=Windows}
Windows is a Microsoft operating system.
:::
::: tab {title=Linux}
Linux is an open-source operating system.
:::
::::
```

On the web the reader sees one at a time; print has no interaction, so the
paged writers render the tabs in sequence, each as a titled block. The
PyMdownX spelling `=== "Windows"` followed by its four-space-indented body is
accepted indefinitely — MkDocs Material renders it natively, and this very page
uses it above — but `:::` is the canonical form and what the printer emits.

= Other containers

The container names TMark knows form a closed registry. Besides the callout
types, `aside`, `figure`, `tabs` and `tab`, there are two layout containers:

```md
::: multicolumn {cols=2}
The content flows in two columns.
:::

::: div {.grid .cards}
A container that means nothing: a hook for classes and an id.
:::
```

A `::: name` whose name is unknown raises `container-unknown` and renders its
content transparently rather than silently becoming a `<div>`.
