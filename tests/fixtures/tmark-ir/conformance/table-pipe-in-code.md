# A `|` inside a code span of a pipe-table cell, and in a column name

GFM splits cells on every `|`, code spans included: the only spelling is
`\|`, which GFM decodes (printer critic U2). Column names are plain
strings and are escaped like cell text.

## input

```md
| a \| b | \*c\* |
| - | - |
| `x \| y` | z |
```

## canonical

```md
| a \| b   | \*c\* |
| -------- | ----- |
| `x \| y` | z     |
```

## ir

```json
{
  "blocks": [
    {
      "type": "Table",
      "model": {
        "settings": {
          "width": "auto"
        },
        "columns": [
          {
            "type": "Leaf",
            "name": "a | b"
          },
          {
            "type": "Leaf",
            "name": "*c*"
          }
        ],
        "rows": [
          {
            "type": "Data",
            "cells": [
              {
                "content": [
                  {
                    "type": "Code",
                    "text": "x | y"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "z"
                  }
                ]
              }
            ]
          }
        ]
      }
    }
  ]
}
```
