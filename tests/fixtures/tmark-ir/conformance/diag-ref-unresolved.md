# Unresolved reference

Spec P4, §Ref: an unresolved reference renders visibly as `[?key]` and
warns; a defined one resolves to its host whatever the case of its prefix.

## input

```md
## Intro {#sec:intro}

See @sec:intro, @Sec:intro and [the intro](#sec:intro), but not @sec:nope.
```

## canonical

```md
## Intro {#sec:intro}

See @sec:intro, @Sec:intro and [the intro](#sec:intro), but not @sec:nope.
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
          "text": "Intro"
        }
      ],
      "attrs": {
        "id": "sec:intro"
      }
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
              "key": "sec:intro"
            }
          ]
        },
        {
          "type": "Str",
          "text": ", "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "Sec:intro"
            }
          ]
        },
        {
          "type": "Str",
          "text": " and "
        },
        {
          "type": "Link",
          "content": [
            {
              "type": "Str",
              "text": "the intro"
            }
          ],
          "target": {
            "type": "Anchor",
            "value": "sec:intro"
          }
        },
        {
          "type": "Str",
          "text": ", but not "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "sec:nope"
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
ref-unresolved @ 3:66-3:74
```
