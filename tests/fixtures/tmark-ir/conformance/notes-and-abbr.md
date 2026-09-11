# Footnotes, comments and acronyms

Spec §Note, §Comment, §Glossary and acronyms.

## input

```md
The HTML spec[^1] is maintained by the W3C. <!-- check the year -->

[^1]: The living standard.

*[HTML]: HyperText Markup Language
*[W3C]: World Wide Web Consortium
```

## canonical

```md
The HTML spec[^1] is maintained by the W3C. <!-- check the year -->

[^1]: The living standard.

*[HTML]: HyperText Markup Language
*[W3C]: World Wide Web Consortium
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "The HTML spec"
        },
        {
          "type": "Note",
          "label": "1"
        },
        {
          "type": "Str",
          "text": " is maintained by the W3C. "
        },
        {
          "type": "Comment",
          "text": " check the year "
        }
      ]
    }
  ],
  "abbreviations": [
    {
      "key": "HTML",
      "expansion": "HyperText Markup Language"
    },
    {
      "key": "W3C",
      "expansion": "World Wide Web Consortium"
    }
  ],
  "footnotes": [
    {
      "label": "1",
      "content": [
        {
          "type": "Para",
          "content": [
            {
              "type": "Str",
              "text": "The living standard."
            }
          ]
        }
      ]
    }
  ]
}
```
