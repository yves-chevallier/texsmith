# Heading attributes

Spec §Attributes, §Header: `{#id .class key=value}` at the end of the line.
The printer writes the id first, then classes, then keys in source order.

## input

```md
## Boot sequence {lang=en #sec:boot .draft}
```

## canonical

```md
## Boot sequence {#sec:boot .draft lang=en}
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
      ],
      "attrs": {
        "id": "sec:boot",
        "classes": [
          "draft"
        ],
        "kv": [
          [
            "lang",
            "en"
          ]
        ]
      }
    }
  ]
}
```
