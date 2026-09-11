# Unknown column in a named row

Design 05 `table-column-unknown`: a named row's key names no top-level data
column (the typo TeXSmith's docs use as the example).

## input

````md
```yaml table
columns:
  - Year
  - {name: Actual, columns: [H1, H2]}
rows:
  - 2024: {Acutal: [6, 7]}
```
````
## canonical

````md
```yaml table
columns:
  - Year
  - {name: Actual, columns: [H1, H2]}
rows:
  - 2024: {Acutal: [6, 7]}
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
            "name": "Year"
          },
          {
            "type": "Group",
            "name": "Actual",
            "columns": [
              {
                "type": "Leaf",
                "name": "H1"
              },
              {
                "type": "Leaf",
                "name": "H2"
              }
            ]
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
                    "text": "2024"
                  }
                ]
              },
              {},
              {}
            ],
            "named": true
          }
        ]
      },
      "source": "columns:\n  - Year\n  - {name: Actual, columns: [H1, H2]}\nrows:\n  - 2024: {Acutal: [6, 7]}"
    }
  ]
}
```

## diagnostics

```text
table-column-unknown @ 1:1-7:4
```
