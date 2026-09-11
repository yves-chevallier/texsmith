# Caret insert with the feature on

Spec §Inline text, Appendix "PyMdownX compatibility profile": with
`inline.insert` on, `^^x^^` is sugar for `{underline}[x]`; the printer
emits the role.

## input

```md
---
press:
  features:
    inline.insert: true
---

Now ^^inserted^^ text.
```

```md
---
press:
  features:
    inline.insert: true
---

Now {underline}[inserted] text.
```

## canonical

```md
---
press:
  features:
    inline.insert: true
---

Now {underline}[inserted] text.
```

## ir

```json
{
  "front_matter": {
    "raw": "---\npress:\n  features:\n    inline.insert: true\n---",
    "keys": {
      "press": {
        "features": {
          "inline.insert": true
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
          "text": "Now "
        },
        {
          "type": "Underline",
          "content": [
            {
              "type": "Str",
              "text": "inserted"
            }
          ]
        },
        {
          "type": "Str",
          "text": " text."
        }
      ]
    }
  ]
}
```

