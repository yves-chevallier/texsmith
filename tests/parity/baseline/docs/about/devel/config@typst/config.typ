#set document(
title: "Global user configuration",
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
#text(size: 1.8em, weight: "bold")[Global user configuration]]
#v(1.5em)

We want TeXSmith to support a global user configuration file located at `.texsmith/config.yml`. This file allows users to set their preferred defaults for templates, Mermaid styles, compilation options, and paper formats. The configuration file is optional and can be placed in the current working directory or any parent directory.

This only affects CLI usage of TeXSmith. The API remains robust and does not depend on any global configuration, except for the cache directory.

A config file could be:

```yaml
template: article
engine: tectonic
paper:
  format: a4
  orientation: portrait
mermaid:
  theme: neutral
callouts:
  style: fancy
```

The format is not rigidly defined. It is used to set default values for command-line options. Command-line options always take precedence over configuration file settings, and YAML front matter in Markdown files has the highest precedence.

Fragments, plugins, and everything else inherit from this global configuration when using the CLI.
