# Invalid placement

Design 05 `table-placement` (lint): a placement that is not made of the
float letters `hHtbpT!`. The model holds the value, so the table prints
from the model.

## input

````md
```yaml table
table: {placement: xyz}
columns: [A, B]
rows:
  - [1, 2]
```
````
## canonical

````md
```yaml table
table:
  placement: xyz
columns:
  - A
  - B
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
          "width": "auto",
          "placement": "xyz"
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
      }
    }
  ]
}
```

## resolution

```text
table-placement @ 1:1-6:4
```
