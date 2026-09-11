# Spans under a three-level header

Spec §Table rung 5: a rectangle span written inside a group list, every
slot it absorbs in the next row acknowledged with `~`, the rest of that
group as a list of the remaining leaves; a column span with an alignment
override inside a list. `long: auto` is the default and is not printed.

## input

````md
```yaml table
table: {long: auto}
columns:
  - Product
  - name: 2024
    columns:
      - {name: H1, columns: [Q1, Q2]}
      - {name: H2, columns: [Q3, Q4]}
rows:
  - [Alpha, [{value: Maria, rows: 2, cols: 2}, 3, 4]]
  - [Beta, ~, ~, [5, 6]]
  - [Gamma, [1, 2, {value: Sum, cols: 2, align: c}]]
```
````
## canonical

````md
```yaml table
columns:
  - Product
  - {name: 2024, columns: [{name: H1, columns: [Q1, Q2]}, {name: H2, columns: [Q3, Q4]}]}
rows:
  - [Alpha, {value: Maria, rows: 2, cols: 2}, [3, 4]]
  - [Beta, ~, ~, [5, 6]]
  - [Gamma, [1, 2, {value: Sum, cols: 2, align: center}]]
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
            "name": "2024",
            "columns": [
              {
                "type": "Group",
                "name": "H1",
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
                "name": "H2",
                "columns": [
                  {
                    "type": "Leaf",
                    "name": "Q3"
                  },
                  {
                    "type": "Leaf",
                    "name": "Q4"
                  }
                ]
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
                    "text": "Alpha"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "Maria"
                  }
                ],
                "rows": 2,
                "cols": 2
              },
              {
                "absorbed": true
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
                    "text": "Beta"
                  }
                ]
              },
              {
                "absorbed": true
              },
              {
                "absorbed": true
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "5"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "6"
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
                    "text": "Gamma"
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
                    "text": "Sum"
                  }
                ],
                "cols": 2,
                "align": "c"
              },
              {
                "absorbed": true
              }
            ]
          }
        ]
      }
    }
  ]
}
```
