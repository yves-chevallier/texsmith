# Front matter

Spec §Front matter: copied byte for byte; keys may sit at the root or under
`press`, `press` wins; unknown keys are preserved.

## input

```md
---
title: Firmware Review
lang: fr
press:
  template: article
  features:
    paragraph.lead: false
---

**Not a lead.** With the feature off.
```

## canonical

```md
---
title: Firmware Review
lang: fr
press:
  template: article
  features:
    paragraph.lead: false
---

**Not a lead.** With the feature off.
```

## ir

```json
{
  "front_matter": {
    "raw": "---\ntitle: Firmware Review\nlang: fr\npress:\n  template: article\n  features:\n    paragraph.lead: false\n---",
    "keys": {
      "title": "Firmware Review",
      "lang": "fr",
      "press": {
        "features": {
          "paragraph.lead": false
        }
      }
    },
    "extra": {
      "press": {
        "template": "article"
      }
    }
  },
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Strong",
          "content": [
            {
              "type": "Str",
              "text": "Not a lead."
            }
          ]
        },
        {
          "type": "Str",
          "text": " With the feature off."
        }
      ]
    }
  ]
}
```
