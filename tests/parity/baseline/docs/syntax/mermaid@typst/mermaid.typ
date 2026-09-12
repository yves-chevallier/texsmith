#set document(
title: "Mermaid Diagrams",
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
#text(size: 1.8em, weight: "bold")[Mermaid Diagrams]]
#v(1.5em)

Just like MkDocs, TeXSmith understands #link("https://mermaid.js.org")[Mermaid] diagrams. Browsers render them on the fly, but PDFs need static assets, so TeXSmith converts each diagram into a vector PDF during the build. That requires either:

+ Installing `mermaid-cli` and its dependencies in your environment, or
+ Using Docker with the pulled image `mermaidjs/mermaid-cli`.

= Inline diagram

A Mermaid fence is a data directive whose node word is `image`:

````md
```mermaid image
flowchart LR
    A --> B
    B --> C
```
````

A bare ```` ```mermaid ```` fence means the same thing — `image` is the one
default that is not `code`, because that is what MkDocs Material and every
Mermaid-aware renderer do with it. The sugar is kept indefinitely for exactly
that reason. To _show_ the source as a listing instead, ask for `mermaid code`:

````md
```mermaid code
flowchart LR
    A --> B
```
````

#figure(
image("<HASH>.png"),
)

= External diagrams

Sometimes diagrams live better outside the Markdown. TeXSmith supports:

+ Reference external `.mmd` / `.mermaid` files.
+ Embed Mermaid Live snippets using `pako:` URLs for live editing.

Diagram sources _are_ images: the extension recognises the format from the
path and converts inline and external sources the same way.

Using a `.mmd` file is as simple as including an image:

```md
![Build pipeline](../assets/mermaid.mmd)
```

#figure(
image("<HASH>.png"),
caption: [Build pipeline],
)

Mermaid Live encodes diagrams via Pako (a compression library) so you can share/edit them through URLs:

```md
![Online Diagram](https://mermaid.live/edit#pako:eNpVTctugzAQ_BVrT4lEEMQEiA_tIemt7aE9tX
EODl4eSrAtY5q2iH8vEBGpe1jtzOzMdJBpicAgv-hrVgrryPMbV2SYxg1o8T7uJVmtHoipsvNhXxWkNcfby8hMU
pV3O3E6iQKbx_6mVfmgcHjVHMaPxqE5vOgvJLm2V2El0Qon9jjXobnX_Iv4wGbO0GbxpOQSPChsJYE526IHNdpa
jBC60cjBlVgjBzacUtgzB676wWOE-tS6nm1Wt0UJLBeXZkCtkcLhvhKFFfWdtagk2p1ulQO23tApBFgH38DCMPG
TMKI0TKKABkHswQ-wlPrxOtrSKNnSOA2SsPfgd2oN_DTZ9H9_ZXFC)
```

When TeXSmith renders HTML/PDF it wraps the image with a link to the Mermaid Live editor. Click the preview to inspect the source:

#figure(
image("<HASH>.png"),
caption: [Example Pako],
)

= #ts-logo("LaTeX") Rendering

Here’s how the diagrams look once TeXSmith embeds them:

#figure(
image("snippet-<HASH>.png"),
)

= Conversion by TeXSmith

All Mermaid diagrams are converted to PDF and included with `\includegraphics`
so they integrate cleanly with templates and #ts-logo("LaTeX") floats.

Add a caption line to promote the diagram to a numbered figure:

```md
![Build pipeline](../assets/mermaid.mmd)

Figure: The documentation build pipeline. {#fig:pipeline}
```

Printed output might deserve a different theme. Point `mermaid_config` to a JSON config (front matter or CLI `–attribute press.mermaid_config=...`) to override:

```yaml
---
press:
  mermaid_config: mermaid-config.json
---
```

Alternatively, you can add a `mermaid-config.json` file to the `~/.texsmith/` directory
to apply it globally to all your TeXSmith projects.
