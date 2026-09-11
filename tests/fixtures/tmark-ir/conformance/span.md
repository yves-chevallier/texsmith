# Anonymous span

Spec §Attributes: `[text]{attrs}` hosts attributes on a piece of text; a
span may hold a link. Brackets without attributes stay plain text.

## input

```md
An anchor on [this claim]{#claim:one}, a [quote with a [link](x.md)]{lang=en}, and [plain brackets].
```

## canonical

```md
An anchor on [this claim]{#claim:one}, a [quote with a [link](x.md)]{lang=en}, and [plain brackets].
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "An anchor on "
        },
        {
          "type": "Span",
          "content": [
            {
              "type": "Str",
              "text": "this claim"
            }
          ],
          "attrs": {
            "id": "claim:one"
          }
        },
        {
          "type": "Str",
          "text": ", a "
        },
        {
          "type": "Span",
          "content": [
            {
              "type": "Str",
              "text": "quote with a "
            },
            {
              "type": "Link",
              "content": [
                {
                  "type": "Str",
                  "text": "link"
                }
              ],
              "target": {
                "type": "Document",
                "value": "x.md"
              }
            }
          ],
          "attrs": {
            "kv": [
              [
                "lang",
                "en"
              ]
            ]
          }
        },
        {
          "type": "Str",
          "text": ", and [plain brackets]."
        }
      ]
    }
  ]
}
```
