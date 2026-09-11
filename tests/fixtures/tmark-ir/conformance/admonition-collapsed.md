# Collapsed admonitions

Spec §Admonition: folding is the `collapsed` attribute; `??? type` and
`???+ type` are class-E sugar.

## input

```md
??? note "Folded"
    Hidden by default.

???+ tip
    Shown by default.
```

```md
::: note {title="Folded" collapsed=true}
Hidden by default.
:::

::: tip {collapsed=false}
Shown by default.
:::
```

## canonical

```md
::: note {title=Folded collapsed=true}
Hidden by default.
:::

::: tip {collapsed=false}
Shown by default.
:::
```

## ir

```json
{
  "blocks": [
    {
      "type": "Admonition",
      "kind": "note",
      "title": [
        {
          "type": "Str",
          "text": "Folded"
        }
      ],
      "content": [
        {
          "type": "Para",
          "content": [
            {
              "type": "Str",
              "text": "Hidden by default."
            }
          ]
        }
      ],
      "attrs": {
        "kv": [
          [
            "collapsed",
            "true"
          ]
        ]
      }
    },
    {
      "type": "Admonition",
      "kind": "tip",
      "content": [
        {
          "type": "Para",
          "content": [
            {
              "type": "Str",
              "text": "Shown by default."
            }
          ]
        }
      ],
      "attrs": {
        "kv": [
          [
            "collapsed",
            "false"
          ]
        ]
      }
    }
  ]
}
```
