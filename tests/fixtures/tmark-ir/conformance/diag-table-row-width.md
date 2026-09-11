# Ragged rows

Design 05 `table-row-width`: a row with fewer or more cells than the
declared columns.

## input

````md
```yaml table
columns: [A, B, C, D]
rows:
  - [x, 1, 2]
  - [y, 1, 2, 3, 4]
```
````
## canonical

````md
```yaml table
columns: [A, B, C, D]
rows:
  - [x, 1, 2]
  - [y, 1, 2, 3, 4]
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
                    "text": "x"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "1"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "2"
                  }
                ]
              },
              {}
            ]
          },
          {
            "type": "Data",
            "cells": [
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "y"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "1"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "2"
                  }
                ]
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
          }
        ]
      },
      "source": "columns: [A, B, C, D]\nrows:\n  - [x, 1, 2]\n  - [y, 1, 2, 3, 4]"
    }
  ]
}
```

## diagnostics

```text
table-row-width @ 1:1-6:4
table-row-width @ 1:1-6:4
```
