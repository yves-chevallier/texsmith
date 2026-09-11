# Index entries, deprecated `{b}` / `{i}` suffixes

Spec Appendix "Deprecation schedule" (C20): `{index}[…]{b}` marks the main
entry (`{index main=true}[…]`); `{index}[…]{i}` was a rendering hint that
becomes content markup (`{index}[*…*]`). Both are consumed with the role
and carry a `deprecated` fix.

## input

```md
Relativity {index}[relativity]{b} and {index}[Einstein][papers]{i}.
```

## canonical

```md
Relativity {index main=true}[relativity] and {index}[Einstein][*papers*].
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
          "main": true
        },
        {
          "type": "Str",
          "text": " and "
        },
        {
          "type": "IndexEntry",
          "path": [
            [
              {
                "type": "Str",
                "text": "Einstein"
              }
            ],
            [
              {
                "type": "Emph",
                "content": [
                  {
                    "type": "Str",
                    "text": "papers"
                  }
                ]
              }
            ]
          ]
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
deprecated @ 1:12-1:34
deprecated @ 1:39-1:67
```
