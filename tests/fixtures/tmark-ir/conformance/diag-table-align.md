# Unknown align value

Design 05 `table-align`: an `align` outside `l`, `c`, `r`, `j` and their
long forms.

## input

````md
```yaml table
columns: [A, {name: B, align: middle}]
rows:
  - [1, 2]
```
````
## canonical

````md
```yaml table
columns: [A, {name: B, align: middle}]
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
      "source": "columns: [A, {name: B, align: middle}]\nrows:\n  - [1, 2]"
    }
  ]
}
```

## diagnostics

```text
table-align @ 1:1-5:4
```
