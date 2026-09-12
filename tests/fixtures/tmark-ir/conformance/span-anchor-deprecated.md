# Anchor written as an empty link

Spec §Attributes: an anchor is a span carrying an id, `[]{#id}`. The
MkDocs/autorefs idiom `[](){#id}` writes the same thing as an empty link
hugging an attribute list — an empty link is no link — so it lowers to the
same zero-width `Span` and reports `deprecated` with the canonical
spelling as its fix (Appendix "Deprecation schedule").

## input

```md
[](){ #myanchor }
```

```md
[]{#myanchor}
```

## canonical

```md
[]{#myanchor}
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Span",
          "attrs": {
            "id": "myanchor"
          }
        }
      ]
    }
  ]
}
```

## diagnostics

```text
deprecated @ 1:1-1:18
```

## latex

```latex
\phantomsection\label{myanchor}
```
