# Link titles containing a backslash

CommonMark decodes `\\` and `\"` in a title; the printer encodes both
(printer critic U11).

## input

```md
[a](b "t\\") [c](d "t\"q") [e](f "t\\\"q")
```

## canonical

```md
[a](b "t\\") [c](d "t\"q") [e](f "t\\\"q")
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
            "value": "b"
          },
          "title": "t\\"
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
              "text": "c"
            }
          ],
          "target": {
            "type": "Url",
            "value": "d"
          },
          "title": "t\"q"
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
              "text": "e"
            }
          ],
          "target": {
            "type": "Url",
            "value": "f"
          },
          "title": "t\\\"q"
        }
      ]
    }
  ]
}
```
