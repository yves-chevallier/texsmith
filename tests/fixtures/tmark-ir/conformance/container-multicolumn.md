# Layout container: multicolumn

Spec §Div: `multicolumn` is a name of the closed container registry, a
`Div{name=multicolumn}` with `cols=` forwarded to the `tsdiv` contract; no
`container-unknown`.

## input

```md
::: multicolumn {cols=2}
- alpha
- beta
- gamma
:::
```

## canonical

```md
::: multicolumn {cols=2}
- alpha
- beta
- gamma
:::
```

## ir

```json
{
  "blocks": [
    {
      "type": "Div",
      "name": "multicolumn",
      "content": [
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
                      "text": "alpha"
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
                      "text": "beta"
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
                      "text": "gamma"
                    }
                  ]
                }
              ]
            }
          ]
        }
      ],
      "attrs": {
        "kv": [
          [
            "cols",
            "2"
          ]
        ]
      }
    }
  ]
}
```

