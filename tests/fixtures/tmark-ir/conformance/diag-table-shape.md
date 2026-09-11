# Values of the wrong shape

Design 05 `table-shape`: `long` that is neither a boolean nor `auto`, and a
cell mapping without `value`.

## input

````md
```yaml table
table: {long: sometimes}
columns: [A, B]
rows:
  - [1, {colour: red}]
```
````
## canonical

````md
```yaml table
table: {long: sometimes}
columns: [A, B]
rows:
  - [1, {colour: red}]
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
                    "text": "1"
                  }
                ]
              },
              {}
            ]
          }
        ]
      },
      "source": "table: {long: sometimes}\ncolumns: [A, B]\nrows:\n  - [1, {colour: red}]"
    }
  ]
}
```

## diagnostics

```text
table-shape @ 1:1-6:4
table-shape @ 1:1-6:4
```
