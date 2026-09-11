# Structure lints

A skipped heading level, a caption id off the convention, and a lead-in
promoted by `paragraph.lead` (information: the formatter writes the role).

## input

```md
# Top

### Skipped

**Note.** Promoted.

| a |
| - |
| 1 |

Table: T. {#fig:t}
```

## canonical

```md
# Top

### Skipped

{lead}[Note.] Promoted.

| a   |
| --- |
| 1   |

Table: T. {#fig:t}
```

## ir

```json
{
  "blocks": [
    {
      "type": "Header",
      "level": 1,
      "content": [
        {
          "type": "Str",
          "text": "Top"
        }
      ]
    },
    {
      "type": "Header",
      "level": 3,
      "content": [
        {
          "type": "Str",
          "text": "Skipped"
        }
      ]
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "Promoted."
        }
      ],
      "lead": [
        {
          "type": "Str",
          "text": "Note."
        }
      ]
    },
    {
      "type": "Table",
      "model": {
        "settings": {
          "width": "auto"
        },
        "columns": [
          {
            "type": "Leaf",
            "name": "a"
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
          "text": "T."
        }
      ],
      "attrs": {
        "id": "fig:t"
      }
    }
  ]
}
```

## resolution

```text
heading-skip @ 3:1-3:12
lead-promotion @ 5:1-5:20
caption-id-off-convention @ 11:1-11:19
prefix-host-mismatch @ 11:1-11:19
```
