# Named-row mode

Spec §Table rung 5: "named-row mode with typo detection". A row maps its
label to the top-level data columns it fills, in the shorthand
`Label: {Column: value}` or the explicit `{label, cells}` form; omitted
columns are empty; a numeric label or column name is its text. The printer
keeps the mode and writes the shorthand.

## input

````md
```yaml table
columns:
  - Product
  - {name: FY23, columns: [Q1, Q2]}
  - {name: FY24, columns: [Q1, Q2]}
rows:
  - Apples: {FY23: [1, 2], FY24: [3, 4]}
  - separator: {label: Stone fruit}
  - label: Cherries
    cells: {FY23: [~, 5]}
  - 2024: {FY24: [6, 7]}
```
````
## canonical

````md
```yaml table
columns:
  - Product
  - {name: FY23, columns: [Q1, Q2]}
  - {name: FY24, columns: [Q1, Q2]}
rows:
  - Apples: {FY23: [1, 2], FY24: [3, 4]}
  - {separator: true, label: Stone fruit}
  - Cherries: {FY23: [~, 5]}
  - 2024: {FY24: [6, 7]}
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
            "name": "Product"
          },
          {
            "type": "Group",
            "name": "FY23",
            "columns": [
              {
                "type": "Leaf",
                "name": "Q1"
              },
              {
                "type": "Leaf",
                "name": "Q2"
              }
            ]
          },
          {
            "type": "Group",
            "name": "FY24",
            "columns": [
              {
                "type": "Leaf",
                "name": "Q1"
              },
              {
                "type": "Leaf",
                "name": "Q2"
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
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "4"
                  }
                ]
              }
            ],
            "named": true
          },
          {
            "type": "Separator",
            "label": "Stone fruit"
          },
          {
            "type": "Data",
            "cells": [
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "Cherries"
                  }
                ]
              },
              {},
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "5"
                  }
                ]
              },
              {},
              {}
            ],
            "named": true
          },
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
              {},
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "6"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "7"
                  }
                ]
              }
            ],
            "named": true
          }
        ]
      }
    }
  ]
}
```
