# Lead-in run-in: the role takes what follows it

Spec §Para: the `{lead}[…]` role at the start of a paragraph is the lead-in
whatever follows it and whatever `paragraph.lead` says — it is the
canonical spelling, not sugar. There is no sugar for this shape: the same
paragraph written `**Boot sequence.** The device…` is a bold run-in
(fixture `lead`).

## input

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
