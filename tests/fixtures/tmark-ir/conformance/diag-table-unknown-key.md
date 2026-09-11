# Unknown table keys

Design 05 `table-unknown-key`: a key the table schema does not know, at
the top level or in the `table:` section (TeXSmith `extra="forbid"`). The
table keeps its source and prints back as typed.

## input

````md
```yaml table
table: {wdith: 100%}
columns: [A, B]
rows:
  - [1, 2]
colour: red
```
````
## canonical

````md
```yaml table
table: {wdith: 100%}
columns: [A, B]
rows:
  - [1, 2]
colour: red
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
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "2"
                  }
                ]
              }
            ]
          }
        ]
      },
      "source": "table: {wdith: 100%}\ncolumns: [A, B]\nrows:\n  - [1, 2]\ncolour: red"
    }
  ]
}
```

## diagnostics

```text
table-unknown-key @ 1:1-7:4
table-unknown-key @ 1:1-7:4
```
