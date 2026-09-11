# Index entries, deprecated registry suffix

Spec Appendix "Deprecation schedule": `{index:registry}[…]` normalises to
`{index registry=…}[…]`.

## input

```md
Relativity {index:physics}[relativity].
```

## canonical

```md
Relativity {index registry=physics}[relativity].
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
          "text": "Relativity "
        },
        {
          "type": "IndexEntry",
          "path": [
            [
              {
                "type": "Str",
                "text": "relativity"
              }
            ]
          ],
          "registry": "physics"
        },
        {
          "type": "Str",
          "text": "."
        }
      ]
    }
  ]
}
```

## diagnostics

```text
deprecated @ 1:12-1:27
```
