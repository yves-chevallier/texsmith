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
![Build pipeline](../assets/mermaid.mmd)
```

![Build pipeline](../assets/mermaid.mmd)

Pako is a compression library that Mermaid Live uses to encode diagrams in URLs for sharing and embedding such as:

```markdown
![Online Diagram](https://mermaid.live/edit#pako:eNpVTctugzAQ_BVrT4lEEMQEiA_tIemt7aE9tX
EODl4eSrAtY5q2iH8vEBGpe1jtzOzMdJBpicAgv-hrVgrryPMbV2SYxg1o8T7uJVmtHoipsvNhXxWkNcfby8hMU
pV3O3E6iQKbx_6mVfmgcHjVHMaPxqE5vOgvJLm2V2El0Qon9jjXobnX_Iv4wGbO0GbxpOQSPChsJYE526IHNdpa
jBC60cjBlVgjBzacUtgzB676wWOE-tS6nm1Wt0UJLBeXZkCtkcLhvhKFFfWdtagk2p1ulQO23tApBFgH38DCMPG
TMKI0TKKABkHswQ-wlPrxOtrSKNnSOA2SsPfgd2oN_DTZ9H9_ZXFC)
```

On rendering in HTML or PDF, TeXSmith will add an hyperlink to the Mermaid Live editor. Try clicking the image below:

![Example Pako](https://mermaid.live/edit#pako:eNpVTctugzAQ_BVrT4lEEMQEiA_tIemt7aE9tXEODl4eSrAtY5q2iH8vEBGpe1jtzOzMdJBpicAgv-hrVgrryPMbV2SYxg1o8T7uJVmtHoipsvNhXxWkNcfby8hMUpV3O3E6iQKbx_6mVfmgcHjVHMaPxqE5vOgvJLm2V2El0Qon9jjXobnX_Iv4wGbO0GbxpOQSPChsJYE526IHNdpajBC60cjBlVgjBzacUtgzB676wWOE-tS6nm1Wt0UJLBeXZkCtkcLhvhKFFfWdtagk2p1ulQO23tApBFgH38DCMPGTMKI0TKKABkHswQ-wlPrxOtrSKNnSOA2SsPfgd2oN_DTZ9H9_ZXFC)

## LaTeX Rendering

Here an example of how diagrams are rendered in LaTeX with TeXSmith:

[![Mermaid Diagrams](../assets/examples/mermaid.png)](../assets/examples/mermaid.pdf)

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

