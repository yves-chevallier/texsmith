# Column widths over 100%

Design 05 `table-width-sum` (lint, warning): the column percentages add up
to more than the table.

## input

````md
```yaml table
columns: [{name: A, width: 60%}, {name: B, width: 50%}]
rows:
  - [1, 2]
```
````
## canonical

````md
```yaml table
columns:
  - {name: A, width: 60%}
  - {name: B, width: 50%}
rows:
  - [1, 2]
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
            "name": "A",
            "width": "60%"
          },
          {
            "type": "Leaf",
            "name": "B",
            "width": "50%"
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
      }
    }
  ]
}
```

## resolution

```text
table-width-sum @ 1:1-5:4
```
