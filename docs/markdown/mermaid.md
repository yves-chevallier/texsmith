# Mermaid Diagrams

TeXSmith can render [Mermaid](https://mermaid.js.org) diagrams directly into
vector PDFs during the conversion pipeline. Use the style that best matches your
authoring workflow.

## Fence the diagram inline

```markdown
```mermaid
%% Example diagram caption
flowchart LR
    A --> B
    B --> C
```
```

- Place an optional caption comment (`%% ...`) at the top of the fence. TeXSmith
  turns the comment into the figure caption in LaTeX.
- Inline charts are perfect for quick design notes that live beside the prose.

## Reference external `.mmd` / `.mermaid` files

```markdown
![Build pipeline](assets/ci.mmd)
```

- The diagram is located relative to the current document first, then to the
  MkDocs project root.
- Supported extensions: `.mmd` and `.mermaid`.
- The image alt text becomes the caption when the diagram file does not contain
  a leading `%%` comment.

## Embed Mermaid Live snippets (`pako:` URLs)

Mermaid Live can export compressed URLs; TeXSmith decodes them automatically:

```markdown
![](https://mermaid.live/edit#pako:eNp...)
```

- Keep the URL intact; TeXSmith downloads, inflates, and renders the diagram.
- Provide alt text so the PDF output has a meaningful caption if the embedded
  payload omits one.

## Rendering notes

- All Mermaid diagrams are converted to PDF and included with `\includegraphics`
  so they integrate cleanly with templates and LaTeX floats.
- Rendered artefacts are cached using the diagram contents as a key. Repeated
  builds skip conversion unless the source changes.
- Ensure the `mermaid-cli` prerequisites are available on CI if you extend the
  strategy. The built-in converter works out of the box inside the TeXSmith
  runtime image.
