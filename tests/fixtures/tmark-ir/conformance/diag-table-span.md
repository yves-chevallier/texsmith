# Span not acknowledged

Design 05 `table-span`: the slots a row span absorbs in the next row must
be `~`; a value there collides with the span.

## input

````md
```yaml table
columns: [A, B, C, D]
rows:
  - [r1, {value: Block, rows: 2, cols: 2}, 3]
  - [r2, a, b, c]
```
````
## canonical

````md
```yaml table
columns: [A, B, C, D]
rows:
  - [r1, {value: Block, rows: 2, cols: 2}, 3]
  - [r2, a, b, c]
```
````

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
            "name": "A"
          },
          {
            "type": "Leaf",
            "name": "B"
          },
          {
            "type": "Leaf",
            "name": "C"
          },
          {
            "type": "Leaf",
            "name": "D"
          }
        ],
        "rows": [
          {
            "type": "Data",
            "cells": [
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "r1"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "Block"
                  }
                ],
                "rows": 2,
                "cols": 2
              },
              {
                "absorbed": true
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "3"
                  }
                ]
              }
            ]
          },
          {
            "type": "Data",
            "cells": [
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "r2"
                  }
                ]
              },
              {
                "absorbed": true
              },
              {
                "absorbed": true
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "c"
                  }
                ]
              }
            ]
          }
        ]
      },
      "source": "columns: [A, B, C, D]\nrows:\n  - [r1, {value: Block, rows: 2, cols: 2}, 3]\n  - [r2, a, b, c]"
    }
  ]
}
```

## diagnostics

```text
table-span @ 1:1-6:4
table-span @ 1:1-6:4
```
