#set document(
title: "Plugin API",
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
#text(size: 1.8em, weight: "bold")[Plugin API]]
#v(1.5em)

Plugins bundle the build-time helpers an IR pass drives — the snippet
compiler's nested build, the MkDocs site-side HTML rewriting — so you can extend
TeXSmith without patching the core parse #ts-script("symbols")[→ ]IR #ts-script("symbols")[→ ]write pipeline.

`texsmith.plugins` exposes a namespace package populated by the MkDocs hook in
`docs/hooks/mkdocs_hooks.py`, re-exporting the maintained plugin modules under
`texsmith.adapters.plugins`.

= Loading plugins

```python
import texsmith.plugins.snippet  # noqa: F401

from texsmith import Document, convert_documents

bundle = convert_documents([Document.from_markdown(Path("intro.md"))])
```

= Authoring your own plugin

+ Create a module (e.g., `texsmith.plugins.acme`) exposing the build-time
helpers your documents need, and an IR pass that calls them.
+ Declare entry points or instruct consumers to `import texsmith.plugins.acme`
before rendering.
+ Optionally provide a MkDocs plugin/hook so documentation builds load your
plugin automatically.

Keep plugin modules small and focused.

= Reference
