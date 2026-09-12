#set document(
title: "Template Discovery",
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
#text(size: 1.8em, weight: "bold")[Template Discovery]]
#v(1.5em)

TeXSmith finds templates from multiple locations in a deterministic order:

+ *Built-ins*: shipped with TeXSmith (`article`, `book`, `letter`, `snippet`).
+ *Installed packages*: PyPI distributions named `texsmith-template-*` (or exposing the `texsmith.templates` entry point).
+ *Local tree*: current working directory and any ancestor `templates/` folder. Any `manifest.toml`/`template/manifest.toml` or `__init__.py` counts as a template root.
+ *User directory*: `~/.texsmith/templates/<name>` (same structure as local).

Use the CLI to inspect what was found:

```bash
texsmith --template-info --template article
texsmith templates  # list all visible templates
```

A valid template root contains either `manifest.toml` or `template/manifest.toml`; an `__init__.py` alongside these allows specialized Python logic.

Notes:

- Passing an explicit path (`–template ./templates/custom`) bypasses discovery order.
- Package roots win over same-named local folders; local folders win over the home directory.
- Template manifests can include a `mermaid-config.json` at the root; `–template-info` will surface it.

To scaffold a built-in for customization:

```bash
texsmith templates scaffold article ./templates/article
```

Then point `–template` to that path. Any `mermaid-config.json` placed at the template root will be picked up automatically.
