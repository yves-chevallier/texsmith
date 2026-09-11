# Unnumbered and unlisted headings

Spec §Header: `.unnumbered` takes a heading out of the numbering sequence,
`.unlisted` also out of the table of contents; each applies to its own
heading over the `press.numbered` default. Pandoc's `{-}` is literal text.

## input

```md
# Preface {.unnumbered}

## Colophon {.unlisted}
```

## canonical

```md
# Preface {.unnumbered}

## Colophon {.unlisted}
```

## ir

```json
{
  "blocks": [
    {
      "type": "Header",
      "level": 1,
      "content": [
        {
          "type": "Str",
          "text": "Preface"
        }
      ],
      "attrs": {
        "classes": [
          "unnumbered"
        ]
      }
    },
    {
      "type": "Header",
      "level": 2,
      "content": [
        {
          "type": "Str",
          "text": "Colophon"
        }
      ],
      "attrs": {
        "classes": [
          "unlisted"
        ]
      }
    }
  ]
}
```

