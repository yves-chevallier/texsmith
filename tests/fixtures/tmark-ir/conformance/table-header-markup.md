# Inline markup in a table header

Spec §Table: "Inline Markdown survives inside cells in all forms" — a
header cell is a cell. The header is kept as `Column.title`; `Column.name`
stays its plain text, the key of named-row mode.

## input

```md
| Key `tlmgr` name | **Bold head** | [Link](https://e.org) |
| ---------------- | ------------- | --------------------- |
| `body code`      | *em*          | plain                 |
```

## canonical

```md
| Key `tlmgr` name | **Bold head** | [Link](https://e.org) |
| ---------------- | ------------- | --------------------- |
| `body code`      | *em*          | plain                 |
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
            "name": "Key tlmgr name",
            "title": [
              {
                "type": "Str",
                "text": "Key "
              },
              {
                "type": "Code",
                "text": "tlmgr"
              },
              {
                "type": "Str",
                "text": " name"
              }
            ]
          },
          {
            "type": "Leaf",
            "name": "Bold head",
            "title": [
              {
                "type": "Strong",
                "content": [
                  {
                    "type": "Str",
                    "text": "Bold head"
                  }
                ]
              }
            ]
          },
          {
            "type": "Leaf",
            "name": "Link",
            "title": [
              {
                "type": "Link",
                "content": [
                  {
                    "type": "Str",
                    "text": "Link"
                  }
                ],
                "target": {
                  "type": "Url",
                  "value": "https://e.org"
                }
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
                    "type": "Code",
                    "text": "body code"
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Emph",
                    "content": [
                      {
                        "type": "Str",
                        "text": "em"
                      }
                    ]
                  }
                ]
              },
              {
                "content": [
                  {
                    "type": "Str",
                    "text": "plain"
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

## latex

```latex
\begin{center}
\begin{tabularx}{\linewidth}{>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}X}
\toprule
\textbf{Key \tscodeinline{tlmgr} name} & \textbf{\textbf{Bold head}} & \textbf{\href{https://e.org}{Link}} \\
\midrule
\tscodeinline{body code} & \emph{em} & plain \\
\bottomrule
\end{tabularx}
\end{center}
```

## typst

```typst
#table(
  columns: 3,
  align: (left, left, left,),
  table.header([Key `tlmgr` name], [*Bold head*], [#link("https://e.org")[Link]]),
  [`body code`], [_em_], [plain],
)
```
