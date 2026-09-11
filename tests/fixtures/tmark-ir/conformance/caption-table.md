# Table caption line

Spec §Caption: the caption is the paragraph adjacent to the float; canonical
position is after the block, the line before the table is accepted sugar
(spec challenge C7 for the attachment rule). The anchor lives on the caption.

## input

```md
| A | B |
| - | - |
| 1 | 2 |

Table: Stock. {#tbl:stock}
```

```md
Table: Stock. {#tbl:stock}

| A | B |
| - | - |
| 1 | 2 |
```

## canonical

```md
| A   | B   |
| --- | --- |
| 1   | 2   |

Table: Stock. {#tbl:stock}
```

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
      }
    },
    {
      "type": "Caption",
      "kind": "table",
      "content": [
        {
          "type": "Str",
          "text": "Stock."
        }
      ],
      "attrs": {
        "id": "tbl:stock"
      }
    }
  ]
}
```
