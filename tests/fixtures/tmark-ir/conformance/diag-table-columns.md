# Too few columns

Design 05 `table-columns`: a `yaml table` needs at least two columns
(TeXSmith `Table.columns: min_length=2`).

## input

````md
```yaml table
columns: [A]
rows:
  - [1]
```
````
## canonical

````md
```yaml table
columns: [A]
rows:
  - [1]
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
              }
            ]
          }
        ]
      },
      "source": "columns: [A]\nrows:\n  - [1]"
    }
  ]
}
```

## diagnostics

```text
table-columns @ 1:1-5:4
```
