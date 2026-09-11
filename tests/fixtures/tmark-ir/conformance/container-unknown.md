# Unknown container

Spec §Div: a `::: name` whose name is unknown is a `Div` and a class-D
error; an unclosed container closes at the end of the document.

## input

```md
::: gadget {x=1}
Body.
```

## canonical

```md
::: gadget {x=1}
Body.
:::
```

## ir

```json
{
  "blocks": [
    {
      "type": "Div",
      "name": "gadget",
      "content": [
        {
          "type": "Para",
          "content": [
            {
              "type": "Str",
              "text": "Body."
            }
          ]
        }
      ],
      "attrs": {
        "kv": [
          [
            "x",
            "1"
          ]
        ]
      }
    }
  ]
}
```

## diagnostics

```text
container-unknown @ 1:1-3:1
container-unclosed @ 1:1-3:1
```
