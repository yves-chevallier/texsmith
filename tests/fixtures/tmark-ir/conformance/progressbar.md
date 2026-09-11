# Progress bar

Spec §ProgressBar: an inline node `{value, label}`; the PyMdownX percentage
spelling is canonical; the fraction form and the Python-Markdown `{: .thin}`
attribute colon are deprecated sugar (Appendix "Deprecation schedule").

## input

```md
[=25% "Research"]
[=9/20 "Review"]{: .thin}
```

```md
[=25% "Research"]
[=45% "Review"]{.thin}
```

## canonical

```md
[=25% "Research"]
[=45% "Review"]{.thin}
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "ProgressBar",
          "value": 25.0,
          "label": "Research"
        },
        {
          "type": "SoftBreak"
        },
        {
          "type": "ProgressBar",
          "value": 45.0,
          "label": "Review",
          "attrs": {
            "classes": [
              "thin"
            ]
          }
        }
      ]
    }
  ]
}
```

## diagnostics

```text
deprecated @ 2:1-2:17
deprecated @ 2:17-2:26
```
