#set document(
title: "Arguments",
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
#text(size: 1.8em, weight: "bold")[Arguments]]
#v(1.5em)

#ts-callout-style.update("fancy")

= Attribute ownership & consumers

- *Owner*: each attribute belongs to either the template (default) or a fragment (`fragment.toml` attributes set `owner = <fragment name>` implicitly). Conflicting owners raise a `TemplateError`.
- *Emitter*: templates can surface derived attributes through `emit` in `manifest.toml` so renderers see both declared attributes and emitted helpers (for example, `callout_style` or `code.engine`).
- *Consumer*: any template/fragment/renderer code that reads the attribute. Consumers should only read attributes they own or that are explicitly emitted.
- Precedence: CLI/front matter overrides #ts-script("symbols")[→ ]attribute resolver (type coercion, normaliser, escape) #ts-script("symbols")[→ ]emitted defaults #ts-script("symbols")[→ ]render-time context.

When adding new attributes, pick a single owner (template or fragment) and document the sources that are allowed to override it.
