# Text Formatting

Like vanilla Markdown, you can apply basic text formatting using a variety of delimiters. TeXSmith extends this with small capitals support.

```markdown
The quick brown fox jumps over the lazy dog. *(regular)*

*The quick brown fox jumps over the lazy dog.* *(italic)*

**The quick brown fox jumps over the lazy dog.** **(bold)*

***The quick brown fox jumps over the lazy dog.*** *(bold italic)*

~~The quick brown fox jumps over the lazy dog.~~ *(strikethrough)*

__The quick brown fox jumps over the lazy dog.__ *(small capitals)*
```

```md { .snippet }
The quick brown fox jumps over the lazy dog. *(regular)*

*The quick brown fox jumps over the lazy dog.* *(italic)*

**The quick brown fox jumps over the lazy dog.** **(bold)*

***The quick brown fox jumps over the lazy dog.*** *(bold italic)*

~~The quick brown fox jumps over the lazy dog.~~ *(strikethrough)*

__The quick brown fox jumps over the lazy dog.__ *(small capitals)*
```

The `pymdownx.betterem` extension lets you stack delimiters for bold italic.

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
