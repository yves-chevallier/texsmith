# Inline sugar

Spec §Inline text, Table "Inline text nodes": the PyMdownX spellings
normalise to roles; `**x**` and `*x*` stay.

## input

```md
Some ==marked==, ~~deleted~~, H~2~O, E=mc^2^, ++ctrl+alt+s++, **bold** and *emph*.
```

```md
Some {mark}[marked], {del}[deleted], H{sub}[2]O, E=mc{sup}[2], {keys}[ctrl+alt+s], **bold** and *emph*.
```

## canonical

```md
Some {mark}[marked], {del}[deleted], H{sub}[2]O, E=mc{sup}[2], {keys}[ctrl+alt+s], **bold** and *emph*.
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
          "text": "Some "
        },
        {
          "type": "Highlight",
          "content": [
            {
              "type": "Str",
              "text": "marked"
            }
          ]
        },
        {
          "type": "Str",
          "text": ", "
        },
        {
          "type": "Strikeout",
          "content": [
            {
              "type": "Str",
              "text": "deleted"
            }
          ]
        },
        {
          "type": "Str",
          "text": ", H"
        },
        {
          "type": "Subscript",
          "content": [
            {
              "type": "Str",
              "text": "2"
            }
          ]
        },
        {
          "type": "Str",
          "text": "O, E=mc"
        },
        {
          "type": "Superscript",
          "content": [
            {
              "type": "Str",
              "text": "2"
            }
          ]
        },
        {
          "type": "Str",
          "text": ", "
        },
        {
          "type": "Keystroke",
          "keys": [
            "ctrl",
            "alt",
            "s"
          ]
        },
        {
          "type": "Str",
          "text": ", "
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
          "text": " and "
        },
        {
          "type": "Emph",
          "content": [
            {
              "type": "Str",
              "text": "emph"
            }
          ]
        },
        {
          "type": "Str",
          "text": "."
        }
      ]
    }
  ]
}
```
