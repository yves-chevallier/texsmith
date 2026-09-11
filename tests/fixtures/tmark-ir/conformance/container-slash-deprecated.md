# Deprecated `///` blocks

Appendix "Deprecation schedule": `/// latex … ///` (and `typst`, `html`)
is a raw fence; `/// caption`, `/// figure-caption`, `/// table-caption`
(pymdownx.blocks.caption, with the indented `attrs: {id: …}` option line)
are a caption line after the float. A generic `caption` takes the kind of
its float; `figure-caption` and `table-caption` name theirs. Every other
`/// name` is a container (`::: name`).

## input

```md
![Melting](mozzarella.svg){width=80%}

/// caption
    attrs: {id: fig:melting}
Melting behavior of high-moisture cheese
upon heating
///

| Cheese | Age |
| ------ | --- |
| Comté  | 18  |

/// table-caption
    attrs: {id: tbl:samples}
Hard cheese samples
///

/// latex
\vspace{1em}
///
```

## canonical

````md
![Melting](mozzarella.svg){width=80%}

Figure: Melting behavior of high-moisture cheese
upon heating {#fig:melting}

| Cheese | Age |
| ------ | --- |
| Comté  | 18  |

Table: Hard cheese samples {#tbl:samples}

```latex raw
\vspace{1em}
```
````

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Image",
          "src": "mozzarella.svg",
          "alt": [
            {
              "type": "Str",
              "text": "Melting"
            }
          ],
          "attrs": {
            "kv": [
              [
                "width",
                "80%"
              ]
            ]
          }
        }
      ]
    },
    {
      "type": "Caption",
      "kind": "figure",
      "content": [
        {
          "type": "Str",
          "text": "Melting behavior of high-moisture cheese"
        },
        {
          "type": "SoftBreak"
        },
        {
          "type": "Str",
          "text": "upon heating"
        }
      ],
      "attrs": {
        "id": "fig:melting"
      }
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
            "name": "Cheese"
          },
          {
            "type": "Leaf",
            "name": "Age"
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
                    "text": "Comté"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "18"
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
          "text": "Hard cheese samples"
        }
      ],
      "attrs": {
        "id": "tbl:samples"
      }
    },
    {
      "type": "RawBlock",
      "format": "latex",
      "text": "\\vspace{1em}"
    }
  ]
}
```

## diagnostics

```text
deprecated @ 3:1-7:4
deprecated @ 13:1-16:4
deprecated @ 18:1-20:4
```
