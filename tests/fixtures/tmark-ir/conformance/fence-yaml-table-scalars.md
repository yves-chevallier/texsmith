# YAML cells that YAML would type

Floats, exponents, signed and prefixed integers and the null and boolean
words in any case are quoted so that they read back as the same text;
plain integers stay plain (printer critic U7). The input is the quoted
form: the unquoted one reads `1.10` as `1.1` and is a different table. The
spanning cell keeps the table out of the pipe form, where the question
does not arise.

## input

````md
```yaml table
columns: [A, B, C]
rows:
  - ["1.10", "+1", "0x1F"]
  - [3, "NULL", "Yes"]
  - [{value: "1e3", cols: 2}, ~, "on"]
```
````

## canonical

````md
```yaml table
columns:
  - A
  - B
  - C
rows:
  - ["1.10", "+1", "0x1F"]
  - [3, "NULL", "Yes"]
  - [{value: "1e3", cols: 2}, ~, "on"]
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
                    "text": "1.10"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "+1"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "0x1F"
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
                    "text": "3"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "NULL"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "Yes"
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
                    "text": "1e3"
                  }
                ],
                "cols": 2
              },
              {
                "absorbed": true
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "on"
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
