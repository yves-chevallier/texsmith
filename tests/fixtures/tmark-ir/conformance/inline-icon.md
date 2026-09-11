# Icon shortcodes

Spec §Emoji and icon shortcodes: a Material icon shortcode lowers to
`Span{.icon media=web}` holding the shortcode as text; print drops it, the
printer writes the shortcode back, and lint hints `icon-web-only`.

## input

```md
Click :material-cog: Settings.
```

## canonical

```md
Click :material-cog: Settings.
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
          "text": "Click "
        },
        {
          "type": "Span",
          "content": [
            {
              "type": "Str",
              "text": ":material-cog:"
            }
          ],
          "attrs": {
            "classes": [
              "icon"
            ],
            "kv": [
              [
                "media",
                "web"
              ]
            ]
          }
        },
        {
          "type": "Str",
          "text": " Settings."
        }
      ]
    }
  ]
}
```

## resolution

```text
icon-web-only @ 1:7-1:21
```
