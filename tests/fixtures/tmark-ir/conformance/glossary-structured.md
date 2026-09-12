# Glossary declaration, structured spelling

Spec §Glossary and acronyms: the same declaration with its parts named —
`style` (a `glossaries` style), `groups` (group key to heading) and the
terms under `entries`. The three structural keys are not terms: `@gls:api`
resolves, `@gls:groups` does not (C50).

## input

```md
---
press:
  declare:
    glossary:
      style: long
      groups:
        core: Core terms
      entries:
        api:
          group: core
          description: An application programming interface.
---

An @gls:api of the core group, but @gls:groups is no term.
```

## canonical

```md
---
press:
  declare:
    glossary:
      style: long
      groups:
        core: Core terms
      entries:
        api:
          group: core
          description: An application programming interface.
---

An @gls:api of the core group, but @gls:groups is no term.
```

## ir

```json
{
  "front_matter": {
    "raw": "---\npress:\n  declare:\n    glossary:\n      style: long\n      groups:\n        core: Core terms\n      entries:\n        api:\n          group: core\n          description: An application programming interface.\n---",
    "keys": {
      "press": {
        "declare": {
          "glossary": {
            "style": "long",
            "groups": {
              "core": {
                "title": "Core terms"
              }
            },
            "entries": {
              "api": {
                "description": "An application programming interface.",
                "group": "core"
              }
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
          "type": "Str",
          "text": "An "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "gls:api"
            }
          ]
        },
        {
          "type": "Str",
          "text": " of the core group, but "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "gls:groups"
            }
          ]
        },
        {
          "type": "Str",
          "text": " is no term."
        }
      ]
    }
  ]
}
```

## resolution

```text
ref-unresolved @ 14:37-14:47
```
