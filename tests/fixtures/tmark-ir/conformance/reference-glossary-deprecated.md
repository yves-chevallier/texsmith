# Glossary reference, deprecated link form

Spec Appendix "Deprecation schedule" (C20): `[](gls:term)` is `@gls:term`, a
bare `Ref` whose key carries the predeclared `gls` prefix. Before, the link
lowered silently to a `Link` with a `gls:` URL.

## input

```md
An [](gls:API) call.
```

## canonical

```md
An @gls:API call.
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
          "text": "An "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "gls:API"
            }
          ]
        },
        {
          "type": "Str",
          "text": " call."
        }
      ]
    }
  ]
}
```

## diagnostics

```text
deprecated @ 1:4-1:15
```
