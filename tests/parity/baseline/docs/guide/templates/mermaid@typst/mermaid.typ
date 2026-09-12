#set document(
title: "Mermaid Configuration",
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
#text(size: 1.8em, weight: "bold")[Mermaid Configuration]]
#v(1.5em)

TeXSmith will automatically pick up a `mermaid-config.json` located at the root of a template (next to `manifest.toml`). The diagrams module passes this config to Mermaid for all diagrams rendered with that template.

= Using a Built-in Template

The built-in `article` template ships with a `mermaid-config.json`. To inspect or override it:

```bash
texsmith --template-info --template article
texsmith templates  # list all discoverable templates
```

To customize, copy the file, adjust options, and point to your modified template directory:

```bash
cp -r $(python - <<'PY'\nfrom texsmith.core.templates import load_template\nfrom pathlib import Path\nt = load_template('article')\nprint(t.root)\nPY) ./templates/article\n# edit ./templates/article/mermaid-config.json\ntexsmith doc.md --template ./templates/article
```

= Adding Mermaid Config to a Custom Template

+ Place `mermaid-config.json` at the template root (same level as `manifest.toml`).
+ TeXSmith will expose the path via `template.extras["mermaid_config"]` so the renderer can pass it to Mermaid.
+ No manifest changes are required; the presence of the file is enough.

Typical options include theme, font, backgroundColor, and securityLevel. See #link("https://mermaid.js.org/config/theming.html") for full reference.
