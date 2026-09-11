# Table config fence

Spec §Table rung 3: a `yaml table-config` fence after a pipe table carries
positional column layout and a `table:` section; a null entry leaves a
column alone. Canonical order: table, config, caption.

## input

````md
| A | B | C |
| - | - | - |
| 1 | 2 | 3 |

```yaml table-config
table:
  width: 100%
columns:
  - ~
  - {align: right, width: X}
  - {align: center, width-group: g}
```

Table: Config. {#tbl:cfg}
````
## canonical

````md
| A   | B   | C   |
| --- | --- | --- |
| 1   | 2   | 3   |

```yaml table-config
table:
  width: 100%
columns:
  - {}
  - {align: right, width: X}
  - {align: center, width-group: g}
```

Table: Config. {#tbl:cfg}
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
          },
          {
            "type": "Leaf",
            "name": "C"
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
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "3"
                  }
                ]
              }
            ]
          }
        ]
      }
    },
    {
      "type": "TableConfig",
      "columns": [
        {},
        {
          "align": "r",
          "width": "X"
        },
        {
          "align": "c",
          "width_group": "g"
        }
      ],
      "settings": {
        "width": "100%"
      }
    },
    {
      "type": "Caption",
      "kind": "table",
      "content": [
        {
          "type": "Str",
          "text": "Config."
        }
      ],
      "attrs": {
        "id": "tbl:cfg"
      }
    }
  ]
}
```
