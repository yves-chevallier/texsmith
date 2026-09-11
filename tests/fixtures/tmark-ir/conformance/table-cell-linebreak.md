# A line break inside a table cell

A cell with a break is not a pipe-table cell: the table prints as a
`yaml table` fence whose scalar writes the break as `\n` (printer critic
U6).

## input

````md
```yaml table
columns: [A, B]
rows:
  - ["a\nb", c]
```
````

## canonical

````md
```yaml table
columns:
  - A
  - B
rows:
  - ["a\nb", c]
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
                    "text": "a"
                  },
                  {
                    "type": "SoftBreak"
                  },
                  {
                    "type": "Str",
                    "text": "b"
                  }
                ]
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
      }
    }
  ]
}
```
