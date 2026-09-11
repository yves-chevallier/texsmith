# Ambiguous key

Spec §Cite: "A key present in two registries is a hard warning." A span
anchor and an inline bibliography entry share `stock`.

## input

```md
---
press:
  sources:
    bibliography:
      stock: {type: misc, title: Stock}
---

[This claim]{#stock} is cited as @stock.
```

## canonical

```md
---
press:
  sources:
    bibliography:
      stock: {type: misc, title: Stock}
---

[This claim]{#stock} is cited as @stock.
```

## ir

```json
{
  "front_matter": {
    "raw": "---\npress:\n  sources:\n    bibliography:\n      stock: {type: misc, title: Stock}\n---",
    "keys": {
      "press": {
        "sources": {
          "bibliography": {
            "stock": {
              "type": "misc",
              "title": "Stock"
            }
          }
        }
      }
    }
  },
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Span",
          "content": [
            {
              "type": "Str",
              "text": "This claim"
            }
          ],
          "attrs": {
            "id": "stock"
          }
        },
        {
          "type": "Str",
          "text": " is cited as "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "stock"
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
ref-ambiguous @ 8:1-8:21
```
