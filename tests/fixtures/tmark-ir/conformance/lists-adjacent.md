# Two lists of the same kind in a row

CommonMark continues a list across a blank line when the marker is the
same: the second list takes the other marker (`*`, `)`) so that the two
stay apart (printer critic U5).

## input

```md
- a

* b

1. c

1) d

- e
```

## canonical

```md
- a

* b

1. c

1) d

- e
```

## ir

```json
{
  "blocks": [
    {
      "type": "BulletList",
      "items": [
        {
          "content": [
            {
              "type": "Para",
              "content": [
                {
                  "type": "Str",
                  "text": "a"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "type": "BulletList",
      "items": [
        {
          "content": [
            {
              "type": "Para",
              "content": [
                {
                  "type": "Str",
                  "text": "b"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "type": "OrderedList",
      "items": [
        {
          "content": [
            {
              "type": "Para",
              "content": [
                {
                  "type": "Str",
                  "text": "c"
                }
              ]
            }
          ]
        }
      ],
      "start": 1,
      "style": "decimal"
    },
    {
      "type": "OrderedList",
      "items": [
        {
          "content": [
            {
              "type": "Para",
              "content": [
                {
                  "type": "Str",
                  "text": "d"
                }
              ]
            }
          ]
        }
      ],
      "start": 1,
      "style": "decimal"
    },
    {
      "type": "BulletList",
      "items": [
        {
          "content": [
            {
              "type": "Para",
              "content": [
                {
                  "type": "Str",
                  "text": "e"
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```
