# An index entry followed by a literal bracket

`{index}` is the one role with several groups: a `[` right after it would
open one more, so the printer escapes it (printer critic U8).

## input

```md
#[a]\[b] and #[c][d]\[e]
```

## canonical

```md
{index}[a]\[b] and {index}[c][d]\[e]
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "IndexEntry",
          "path": [
            [
              {
                "type": "Str",
                "text": "a"
              }
            ]
          ]
        },
        {
          "type": "Str",
          "text": "[b] and "
        },
        {
          "type": "IndexEntry",
          "path": [
            [
              {
                "type": "Str",
                "text": "c"
              }
            ],
            [
              {
                "type": "Str",
                "text": "d"
              }
            ]
          ]
        },
        {
          "type": "Str",
          "text": "[e]"
        }
      ]
    }
  ]
}
```
