# Quoted attribute values with `"` and `\` inside

Spec §Lexical grammar: a quoted value is `"(?:[^"\\]|\\.)*"`; `\"` and `\\`
decode inside it (challenge C25, resolved). The printer quotes a value that
holds whitespace, `}`, `"`, `=` or `\` and encodes both.

## input

```md
# H {#sec:q k="a \"b\" c" j="x}y" l="p\\q"}
```

## canonical

```md
# H {#sec:q k="a \"b\" c" j="x}y" l="p\\q"}
```

## ir

```json
{
  "blocks": [
    {
      "type": "Header",
      "level": 1,
      "content": [
        {
          "type": "Str",
          "text": "H"
        }
      ],
      "attrs": {
        "id": "sec:q",
        "kv": [
          [
            "k",
            "a \"b\" c"
          ],
          [
            "j",
            "x}y"
          ],
          [
            "l",
            "p\\q"
          ]
        ]
      }
    }
  ]
}
```
