# YAML table

Spec §Table, rung 5: the fully structured form, with grouped headers, spans
and a separator.

## input

````md
```yaml table
columns:
  - Fruit
  - {name: Warehouses, columns: [Geneva, Zurich]}
rows:
  - [Apples, 3, 4]
  - [{value: Total, cols: 3}, ~, ~]
```

Table: Stock by warehouse. {#tbl:stock}
````

## canonical

````md
```yaml table
columns:
  - Fruit
  - {name: Warehouses, columns: [Geneva, Zurich]}
rows:
  - [Apples, 3, 4]
  - [{value: Total, cols: 3}, ~, ~]
```

Table: Stock by warehouse. {#tbl:stock}
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
            "name": "Fruit"
          },
          {
            "type": "Group",
            "name": "Warehouses",
            "columns": [
              {
                "type": "Leaf",
                "name": "Geneva"
              },
              {
                "type": "Leaf",
                "name": "Zurich"
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
                    "text": "Apples"
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
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "4"
                  }
                ]
              }
            ]
          },
          {
            "type": "Data",
            "cells": [
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "Total"
                  }
                ],
                "cols": 3
              },
              {
                "absorbed": true
              },
              {
                "absorbed": true
              }
            ]
          }
        ]
      }
    },
    {
      "type": "Caption",
      "kind": "table",
      "content": [
        {
          "type": "Str",
          "text": "Stock by warehouse."
        }
      ],
      "attrs": {
        "id": "tbl:stock"
      }
    }
  ]
}
```
