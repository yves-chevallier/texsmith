# Missing include and inventory

Spec §Includes and §Cross-document references: a file that does not exist
warns; the reference through the missing inventory is unresolved.

## input

```md
---
press:
  sources:
    crossrefs: {fwrev: build/fw.refs.json}
---

{include}(chapters/boot.md)

See @fwrev:fw:x.
```

## canonical

```md
---
press:
  sources:
    crossrefs: {fwrev: build/fw.refs.json}
---

{include}(chapters/boot.md)

See @fwrev:fw:x.
```

## ir

```json
{
  "front_matter": {
    "raw": "---\npress:\n  sources:\n    crossrefs: {fwrev: build/fw.refs.json}\n---",
    "keys": {
      "press": {
        "sources": {
          "crossrefs": {
            "fwrev": "build/fw.refs.json"
          }
        }
      }
    }
  },
  "blocks": [
    {
      "type": "Include",
      "path": "chapters/boot.md"
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "See "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "fwrev:fw:x"
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
crossref-inventory-missing @ 1:1-5:4
include-missing @ 7:1-7:28
ref-unresolved @ 9:6-9:16
```
