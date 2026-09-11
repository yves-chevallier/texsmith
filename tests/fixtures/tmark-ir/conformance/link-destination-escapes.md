# Link and image destinations that CommonMark cannot read bare

A destination with whitespace, `<`, `>` or unbalanced parentheses prints as
`<…>` (CommonMark §Links); the others stay bare. The printer critic's U3.

## input

```md
[a](<b c>) [d](<e)f>) [g](<#h i>) ![j](<k l.png>) [m](n(o)p)
```

## canonical

```md
[a](<b c>) [d](<e)f>) [g](<#h i>) ![j](<k l.png>) [m](n(o)p)
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Link",
          "content": [
            {
              "type": "Str",
              "text": "a"
            }
          ],
          "target": {
            "type": "Url",
            "value": "b c"
          }
        },
        {
          "type": "Str",
          "text": " "
        },
        {
          "type": "Link",
          "content": [
            {
              "type": "Str",
              "text": "d"
            }
          ],
          "target": {
            "type": "Url",
            "value": "e)f"
          }
        },
        {
          "type": "Str",
          "text": " "
        },
        {
          "type": "Link",
          "content": [
            {
              "type": "Str",
              "text": "g"
            }
          ],
          "target": {
            "type": "Anchor",
            "value": "h i"
          }
        },
        {
          "type": "Str",
          "text": " "
        },
        {
          "type": "Image",
          "src": "k l.png",
          "alt": [
            {
              "type": "Str",
              "text": "j"
            }
          ]
        },
        {
          "type": "Str",
          "text": " "
        },
        {
          "type": "Link",
          "content": [
            {
              "type": "Str",
              "text": "m"
            }
          ],
          "target": {
            "type": "Url",
            "value": "n(o)p"
          }
        }
      ]
    }
  ]
}
```
