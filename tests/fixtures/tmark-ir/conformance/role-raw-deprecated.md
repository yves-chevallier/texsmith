# Raw passthrough, deprecated role

Spec Appendix "Deprecation schedule": `{latex}[…]` becomes `{raw latex}(…)`.

## input

```md
A page break {latex}[\clearpage] here.
```

## canonical

```md
A page break {raw latex}(\clearpage) here.
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "A page break "
        },
        {
          "type": "RawInline",
          "format": "latex",
          "text": "\\clearpage"
        },
        {
          "type": "Str",
          "text": " here."
        }
      ]
    }
  ]
}
```

## diagnostics

```text
deprecated @ 1:14-1:33
```
