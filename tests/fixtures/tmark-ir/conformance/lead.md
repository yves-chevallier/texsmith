# Lead-in paragraph

Spec §Para: `{lead}[…]` is canonical; the `paragraph.lead` feature promotes
a paragraph that *is* one strong span under 80 characters. A strong span
that merely opens a paragraph stays a bold run-in.

## input

```md
**Boot sequence.**

**Leading bold:** the device powers the flash.
```

```md
{lead}[Boot sequence.]

**Leading bold:** the device powers the flash.
```

## canonical

```md
{lead}[Boot sequence.]

**Leading bold:** the device powers the flash.
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "lead": [
        {
          "type": "Str",
          "text": "Boot sequence."
        }
      ]
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Strong",
          "content": [
            {
              "type": "Str",
              "text": "Leading bold:"
            }
          ]
        },
        {
          "type": "Str",
          "text": " the device powers the flash."
        }
      ]
    }
  ]
}
```
