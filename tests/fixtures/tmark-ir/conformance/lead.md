# Lead-in paragraph

Spec §Para: `{lead}[…]` is canonical; a short leading strong span is
promoted by the `paragraph.lead` feature.

## input

```md
**Boot sequence.** The device powers the flash before the SoC.
```

```md
{lead}[Boot sequence.] The device powers the flash before the SoC.
```

## canonical

```md
{lead}[Boot sequence.] The device powers the flash before the SoC.
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
          "text": "The device powers the flash before the SoC."
        }
      ],
      "lead": [
        {
          "type": "Str",
          "text": "Boot sequence."
        }
      ]
    }
  ]
}
```
