# `<div markdown>` container

Spec §Div: an HTML block whose opening tag carries `markdown` (`md_in_html`)
is sugar for a container named after the tag, `id` and `class` becoming the
attribute list; `<div markdown>` is `::: div`, class E, kept indefinitely.

## input

```md
<div class="grid cards" markdown>
Some **bold** inside.
</div>
```

```md
::: div {.grid .cards}
Some **bold** inside.
:::
```

## canonical

```md
::: div {.grid .cards}
Some **bold** inside.
:::
```

## ir

```json
{
  "blocks": [
    {
      "type": "Div",
      "name": "div",
      "content": [
        {
          "type": "Para",
          "content": [
            {
              "type": "Str",
              "text": "Some "
            },
            {
              "type": "Strong",
              "content": [
                {
                  "type": "Str",
                  "text": "bold"
                }
              ]
            },
            {
              "type": "Str",
              "text": " inside."
            }
          ]
        }
      ],
      "attrs": {
        "classes": [
          "grid",
          "cards"
        ]
      }
    }
  ]
}
```

