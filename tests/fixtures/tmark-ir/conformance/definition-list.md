# Definition list

Spec §DefinitionList: PHP-Markdown-Extra `def_list`.

## input

```md
Term
:   Definition, indented continuation lines aligned.

    Second paragraph of the definition.
:   Second definition.

Other
:   Its definition.
```

## canonical

```md
Term
:   Definition, indented continuation lines aligned.

    Second paragraph of the definition.
:   Second definition.

Other
:   Its definition.
```

## ir

```json
{
  "blocks": [
    {
      "type": "DefinitionList",
      "items": [
        [
          [
            {
              "type": "Str",
              "text": "Term"
            }
          ],
          [
            [
              {
                "type": "Para",
                "content": [
                  {
                    "type": "Str",
                    "text": "Definition, indented continuation lines aligned."
                  }
                ]
              },
              {
                "type": "Para",
                "content": [
                  {
                    "type": "Str",
                    "text": "Second paragraph of the definition."
                  }
                ]
              }
            ],
            [
              {
                "type": "Para",
                "content": [
                  {
                    "type": "Str",
                    "text": "Second definition."
                  }
                ]
              }
            ]
          ]
        ],
        [
          [
            {
              "type": "Str",
              "text": "Other"
            }
          ],
          [
            [
              {
                "type": "Para",
                "content": [
                  {
                    "type": "Str",
                    "text": "Its definition."
                  }
                ]
              }
            ]
          ]
        ]
      ]
    }
  ]
}
```
