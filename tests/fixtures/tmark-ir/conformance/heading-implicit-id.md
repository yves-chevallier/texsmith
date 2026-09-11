# Heading implicit id

Spec §Header: a heading without `{#id}` has an implicit id derived at
resolution with the GitHub rule; it is a label like any other, never stored
or printed, and a reference to it is the hint `ref-implicit-id`.

## input

```md
## Boot sequence

See [](#boot-sequence) and @boot-sequence.
```

## canonical

```md
## Boot sequence

See [](#boot-sequence) and @boot-sequence.
```

## ir

```json
{
  "blocks": [
    {
      "type": "Header",
      "level": 2,
      "content": [
        {
          "type": "Str",
          "text": "Boot sequence"
        }
      ]
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "See "
        },
        {
          "type": "Link",
          "target": {
            "type": "Anchor",
            "value": "boot-sequence"
          }
        },
        {
          "type": "Str",
          "text": " and "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "boot-sequence"
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

## resolution

```text
ref-implicit-id @ 3:5-3:23
ref-implicit-id @ 3:28-3:42
```
