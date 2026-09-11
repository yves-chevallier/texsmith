# Lists and task items

Spec §BulletList, OrderedList: `-` and `1.`; task items are class C.

## input

```md
- [ ] open
- [x] done with @sec:intro
- plain

3. third
4. fourth
```

## canonical

```md
- [ ] open
- [x] done with @sec:intro
- plain

3. third
4. fourth
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
                  "text": "open"
                }
              ]
            }
          ],
          "task": "open"
        },
        {
          "content": [
            {
              "type": "Para",
              "content": [
                {
                  "type": "Str",
                  "text": "done with "
                },
                {
                  "type": "Ref",
                  "items": [
                    {
                      "key": "sec:intro"
                    }
                  ]
                }
              ]
            }
          ],
          "task": "done"
        },
        {
          "content": [
            {
              "type": "Para",
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
                  "text": "third"
                }
              ]
            }
          ]
        },
        {
          "content": [
            {
              "type": "Para",
              "content": [
                {
                  "type": "Str",
                  "text": "fourth"
                }
              ]
            }
          ]
        }
      ],
      "start": 3,
      "style": "decimal"
    }
  ]
}
```
