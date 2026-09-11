# Table settings, width groups and a footer

Spec §Table rung 5: the `table:` section (`width`, `placement`, `long`),
`width-group` on columns, a labelled double-rule separator in its nested
form and a footer. The `table:` section prints first; the separator prints
in its flat form.

## input

````md
```yaml table
table:
  width: 100%
  placement: htbp
  long: true
columns:
  - Category
  - {name: Q1, width-group: quarter, align: right}
  - {name: Q2, width-group: quarter, align: right}
rows:
  - [Salaries, 120, 122]
  - separator:
      label: Totals
      double-rule: true
footer:
  - [Total, 120, 122]
```
````
## canonical

````md
```yaml table
table:
  width: 100%
  placement: htbp
  long: true
columns:
  - Category
  - {name: Q1, align: right, width-group: quarter}
  - {name: Q2, align: right, width-group: quarter}
rows:
  - [Salaries, 120, 122]
  - {separator: true, label: Totals, double-rule: true}
footer:
  - [Total, 120, 122]
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
          "width": "100%",
          "placement": "htbp",
          "long": true
        },
        "columns": [
          {
            "type": "Leaf",
            "name": "Category"
          },
          {
            "type": "Leaf",
            "name": "Q1",
            "align": "r",
            "width_group": "quarter"
          },
          {
            "type": "Leaf",
            "name": "Q2",
            "align": "r",
            "width_group": "quarter"
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
                    "text": "Salaries"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "120"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "122"
                  }
                ]
              }
            ]
          },
          {
            "type": "Separator",
            "label": "Totals",
            "double_rule": true
          }
        ],
        "footer": [
          {
            "type": "Data",
            "cells": [
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "Total"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "120"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "122"
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
