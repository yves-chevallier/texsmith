# Figure container

Spec §Image, Figure: `::: figure {cols=2}` groups subfigures; the caption
line is a `Figure:` line inside the container.

## input

```md
::: figure {cols=2}
![Boot](boot.png){#fig:boot}
![Crash](crash.png){#fig:crash}

Figure: Watchdog traces before and after the fix. {#fig:traces}
:::
```

## canonical

```md
::: figure {cols=2}
![Boot](boot.png){#fig:boot}
![Crash](crash.png){#fig:crash}

Figure: Watchdog traces before and after the fix. {#fig:traces}
:::
```

## ir

```json
{
  "blocks": [
    {
      "type": "Figure",
      "content": [
        {
          "type": "Para",
          "content": [
            {
              "type": "Image",
              "src": "boot.png",
              "alt": [
                {
                  "type": "Str",
                  "text": "Boot"
                }
              ],
              "attrs": {
                "id": "fig:boot"
              }
            },
            {
              "type": "SoftBreak"
            },
            {
              "type": "Image",
              "src": "crash.png",
              "alt": [
                {
                  "type": "Str",
                  "text": "Crash"
                }
              ],
              "attrs": {
                "id": "fig:crash"
              }
            }
          ]
        },
        {
          "type": "Caption",
          "kind": "figure",
          "content": [
            {
              "type": "Str",
              "text": "Watchdog traces before and after the fix."
            }
          ],
          "attrs": {
            "id": "fig:traces"
          }
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
