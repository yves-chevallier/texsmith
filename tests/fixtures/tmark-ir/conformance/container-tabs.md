# Tabs

Spec §Tabs: `:::: tabs` holds `::: tab {title=…}` containers; the PyMdownX
`=== "Title"` line plus its indented body is class-E sugar, kept
indefinitely. Paged writers render the tabs in sequence as titled blocks.
The printer separates the tabs by a blank line, as it does any two blocks.

## input

```md
=== "Windows"

    Windows is a Microsoft operating system.

=== "Linux"

    Linux is an open-source operating system.
```

```md
:::: tabs
::: tab {title=Windows}
Windows is a Microsoft operating system.
:::
::: tab {title=Linux}
Linux is an open-source operating system.
:::
::::
```

## canonical

```md
:::: tabs
::: tab {title=Windows}
Windows is a Microsoft operating system.
:::

::: tab {title=Linux}
Linux is an open-source operating system.
:::
::::
```

## ir

```json
{
  "blocks": [
    {
      "type": "Div",
      "name": "tabs",
      "content": [
        {
          "type": "Div",
          "name": "tab",
          "content": [
            {
              "type": "Para",
              "content": [
                {
                  "type": "Str",
                  "text": "Windows is a Microsoft operating system."
                }
              ]
            }
          ],
          "attrs": {
            "kv": [
              [
                "title",
                "Windows"
              ]
            ]
          }
        },
        {
          "type": "Div",
          "name": "tab",
          "content": [
            {
              "type": "Para",
              "content": [
                {
                  "type": "Str",
                  "text": "Linux is an open-source operating system."
                }
              ]
            }
          ],
          "attrs": {
            "kv": [
              [
                "title",
                "Linux"
              ]
            ]
          }
        }
      ]
    }
  ]
}
```

