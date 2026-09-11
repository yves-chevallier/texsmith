# Aside role, deprecated spellings

Spec Appendix Deprecation schedule: `{margin}[…]{l}` normalises to
`{aside side=left}[…]` with a `deprecated` diagnostic.

## input

```md
Hooke's law {margin}[linear only]{l} holds.
```

## canonical

```md
Hooke's law {aside side=left}[linear only] holds.
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
          "text": "Hooke's law "
        },
        {
          "type": "Aside",
          "content": [
            {
              "type": "Plain",
              "content": [
                {
                  "type": "Str",
                  "text": "linear only"
                }
              ]
            }
          ],
          "side": "left"
        },
        {
          "type": "Str",
          "text": " holds."
        }
      ]
    }
  ]
}
```

## diagnostics

```text
deprecated @ 1:13-1:37
```
