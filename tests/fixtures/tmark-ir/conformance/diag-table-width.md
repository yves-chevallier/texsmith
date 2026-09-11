# Percentage width out of range

Design 05 `table-width` (lint): a percentage width outside (0, 100], on
the table or on a column.

## input

````md
```yaml table
table: {width: 150%}
columns: [A, {name: B, width: 0%}]
rows:
  - [1, 2]
```
````
## canonical

````md
```yaml table
table:
  width: 150%
columns:
  - A
  - {name: B, width: 0%}
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
          "width": "150%"
        },
        "columns": [
          {
            "type": "Leaf",
            "name": "A"
          },
          {
            "type": "Leaf",
            "name": "B",
            "width": "0%"
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
table-width @ 1:1-6:4
table-width @ 1:1-6:4
```
