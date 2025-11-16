# Text Formatting 

## Emphsis

You can make text **bold**, *italic*, or ~~strikethrough~~ using the following syntax:

```markdown
This is **bold** text.
This is *italic* text.
This is ~~strikethrough~~ text.
```

With ***PymDown betterem***, you can also achieve bold and italic text by combining the markers:

```markdown
This is ***bold and italic*** text.
```

## Small Capitals

In LaTeX, you can use `\textsc{}` for __small capitals__ text. TeXSmith recycles the old bold syntax for this purpose. The following Markdown:

```markdown
This is __small capitals__ text.
```

Is converted to:

```latex
This is \textsc{small capitals} text.
```

!!! note 
    In MkDocs, you need to specify how to render small capitals using a custom CSS:

    ```css
    .texsmith-smallcaps {
        font-variant: small-caps;
        letter-spacing: 0.04em;
    }
    ```

    Then, include this CSS in your MkDocs configuration under `extra_css`:

    ```yaml
    extra_css:
      - stylesheets/smallcaps.css
    ```