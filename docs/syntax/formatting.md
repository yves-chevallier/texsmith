# Text Formatting

## Emphasis

You can make text **bold**, *italic*, or ~~strikethrough~~ using the following syntax:

```markdown
This is **bold** text.
This is *italic* text.
This is ~~strikethrough~~ text.
```

The `pymdownx.betterem` extension lets you stack delimiters for bold italic:

```markdown
This is ***bold and italic*** text.
```

## Small Capitals

LaTeX uses `\textsc{}` for __small capitals__. TeXSmith remaps the legacy double-underscore syntax to that command:

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
