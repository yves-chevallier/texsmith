# Glossary declaration, flat spelling

Spec §Glossary and acronyms: `declare.glossary` as a mapping of term to
definition, the definition either a string or an object with `name` and
`description`. Every key of the mapping is a term, and `@gls:term`
resolves against it (C50).

## input

```md
---
press:
  declare:
    glossary:
      api: An application programming interface.
      solid: {name: SOLID, description: Five design principles}
---

An @gls:api built on @gls:solid, but not @gls:nope.
```

## canonical

```md
---
press:
  declare:
    glossary:
      api: An application programming interface.
      solid: {name: SOLID, description: Five design principles}
---

An @gls:api built on @gls:solid, but not @gls:nope.
```

## ir

```json
{
  "front_matter": {
    "raw": "---\npress:\n  declare:\n    glossary:\n      api: An application programming interface.\n      solid: {name: SOLID, description: Five design principles}\n---",
    "keys": {
      "press": {
        "declare": {
          "glossary": {
            "entries": {
              "api": {
                "description": "An application programming interface."
              },
              "solid": {
                "name": "SOLID",
                "description": "Five design principles"
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
          "text": " built on "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "gls:solid"
            }
          ]
        },
        {
          "type": "Str",
          "text": ", but not "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "gls:nope"
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
ref-unresolved @ 9:43-9:51
```
