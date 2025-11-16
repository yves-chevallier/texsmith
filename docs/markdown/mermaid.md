# Mermaid Diagrams

À l'instar de MkDocs, TeXSmith can render [Mermaid](https://mermaid.js.org) diagrams. However, as with MkDocs diagrams are live-rendered into the browser, for PDF production, 
TeXSmith converts them to vector PDFs during the conversion pipeline. This would require either

1. Installing `mermaid-cli` and its dependencies in your environment, or
2. Using Docker with the pulled image `mermaidjs/mermaid-cli`.

## Inline diagram

````markdown
```mermaid
flowchart LR
    A --> B
    B --> C
```
````

```mermaid
flowchart LR
    A --> B
    B --> C
```

## External diagrams

Sometime diagrams are better maintained in separate files. TeXSmith supports two ways to include them.

1. Reference external `.mmd` / `.mermaid` files.
2. Embed Mermaid Live snippets using `pako:` URLs for live editing.

Thanks to the `texsmith.mermaid` extension, you can include external Mermaid diagrams in your documents.
The extension will convert them into standard mermaid diagrams during the Markdown processing stage.
It is thus transparent to the pipeline whether the diagram is inline or external.
  
Using a `mmd` file is as simple as including an image:

```markdown
![Build pipeline](assets/ci.mmd)
```

Pako is a compression library that Mermaid Live uses to encode diagrams in URLs for sharing and embedding such as:

```markdown
![Online Diagram](https://mermaid.live/edit#pako:eNpVjcFuwjAMhl8l8mmTABEKzchh0igbF6TtwGktB4uapoImVZq
KsbbvvrQIbfPJ1vf9vxs4mJRAwvFsLgeF1rHdOtHMz0scKZtXrsBqz8bj53ZDjhVG07Vlq4eNYZUyZZnr7PHmr3qJRc2214g5let
Td0PRkH_X1LJ1vMXSmXL_l-wupmWvcf6hfP1_oiz51Ft8RHnE8QEti9AOCowgs3kK0tmaRlCQLbA_oelpAk5RQQlIv6ZoTwkkuvO
ZEvWnMcU9Zk2dKfDd58pfdZmio3WOmcVfhXRKNjK1diC5GCpANvAFMuB8Ivg8mC45D0XYwyvIhZiEs_lSTAM-n81CEXQj-B5-Tid
PYtH9AECMcsA)
```

On rendering in HTML or PDF, TeXSmith will add an hyperlink to the Mermaid Live editor. Try clicking the image below:

![Example Pako](https://mermaid.live/edit#pako:eNpVjcFuwjAMhl8l8mmTABEKzchh0igbF6TtwGktB4uapoImVZqKsbbvvrQIbfPJ1vf9vxs4mJRAwvFsLgeF1rHdOtHMz0scKZtXrsBqz8bj53ZDjhVG07Vlq4eNYZUyZZnr7PHmr3qJRc2214g5letTd0PRkH_X1LJ1vMXSmXL_l-wupmWvcf6hfP1_oiz51Ft8RHnE8QEti9AOCowgs3kK0tmaRlCQLbA_oelpAk5RQQlIv6ZoTwkkuvOZEvWnMcU9Zk2dKfDd58pfdZmio3WOmcVfhXRKNjK1diC5GCpANvAFMuB8Ivg8mC45D0XYwyvIhZiEs_lSTAM-n81CEXQj-B5-TidPYtH9AECMcsA)

## Conversion by TeXSmith

All Mermaid diagrams are converted to PDF and included with `\includegraphics`
so they integrate cleanly with templates and LaTeX floats.

On printed documents you may want to adjust the style of the diagrams to
better suit the medium. You can provide a custom configuration file by setting
the `mermaid_config` attribute either in front matter or via the CLI:

```yaml
---
press:
  mermaid_config: mermaid-config.json
---
```

Alternatively, you can add a `mermaid-config.json` file to the `~/.texsmith/` directory
to apply it globally to all your TeXSmith projects.