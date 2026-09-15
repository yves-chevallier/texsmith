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

#ts-callout-style.update("fancy")

TeXSmith will automatically pick up a `mermaid-config.json` sitting next to the template's `manifest.toml`. The `assets` pass passes this config to Mermaid for every diagram rendered with that template.

= Using a Built-in Template

The built-in `article` template ships with a `mermaid-config.json`. To inspect or override it:

```bash
texsmith --list-templates                    # every discoverable template and its path
texsmith --template article --template-info  # what this one declares
```

To customize, scaffold the template into your tree, adjust the file, and point `–template` at the copy:

```bash
texsmith --template article --template-scaffold ./templates/article
$EDITOR ./templates/article/template/mermaid-config.json
texsmith doc.md --template ./templates/article
```

= Adding Mermaid Config to a Custom Template

+ Place `mermaid-config.json` next to `manifest.toml`.
+ TeXSmith will expose the path via `template.extras["mermaid_config"]` so the renderer can pass it to Mermaid.
+ No manifest changes are required; the presence of the file is enough.

Typical options include theme, font, backgroundColor, and securityLevel. See #link("https://mermaid.js.org/config/theming.html") for full reference.
