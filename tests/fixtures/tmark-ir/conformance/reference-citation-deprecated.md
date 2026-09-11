# Deprecated citation forms

Spec §Cite, Appendix "Deprecation schedule" (decision X7): `[^key]` with no
`[^key]:` definition and `^[k1,k2]` groups are citations, lowered to a
bracketed `Ref` with a `deprecated` fix to `@key` / `@[k1; k2]`. A bare DOI
takes the `doi:` prefix. `^[` never opens a caret superscript, so two
groups in one paragraph never swallow the prose between them. A defined
label (`[^note]`) stays a footnote, a numeric one (`[^1]`) stays literal
(the parser's smoke tests cover it).
A group hugging the word before it (`tutor.^[ein05]`) prints with a space
(`tutor. @ein05`), which the X4 guard needs; see the printer's tests.

## input

```md
Slow to talk [^ein05], said the tutor. ^[ein05,AI2027] He failed the test, ^[10.1007/s00016-014-0153-5] see ^[AI2027] and [^note].

[^note]: A real footnote.
```

## canonical

```md
Slow to talk @ein05, said the tutor. @[ein05; AI2027] He failed the test, @doi:10.1007/s00016-014-0153-5 see @AI2027 and [^note].

[^note]: A real footnote.
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
          "text": "Slow to talk "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "ein05"
            }
          ]
        },
        {
          "type": "Str",
          "text": ", said the tutor. "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "ein05"
            },
            {
              "key": "AI2027"
            }
          ]
        },
        {
          "type": "Str",
          "text": " He failed the test, "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "doi:10.1007/s00016-014-0153-5"
            }
          ]
        },
        {
          "type": "Str",
          "text": " see "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "AI2027"
            }
          ]
        },
        {
          "type": "Str",
          "text": " and "
        },
        {
          "type": "Note",
          "label": "note"
        },
        {
          "type": "Str",
          "text": "."
        }
      ]
    }
  ],
  "footnotes": [
    {
      "label": "note",
      "content": [
        {
          "type": "Para",
          "content": [
            {
              "type": "Str",
              "text": "A real footnote."
            }
          ]
        }
      ]
    }
  ]
}
```

## diagnostics

```text
deprecated @ 1:14-1:22
deprecated @ 1:40-1:55
deprecated @ 1:76-1:104
deprecated @ 1:109-1:118
```
