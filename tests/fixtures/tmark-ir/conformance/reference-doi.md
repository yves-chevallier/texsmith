# DOI citations

Spec §Cite: `@doi:…` cites a DOI in place; `@https://doi.org/…` is
indefinite sugar for it (design C3 allows `/` in these keys).

## input

```md
Cite @doi:10.1002/andp.19053221004 and @https://doi.org/10.1002/andp.19053221004.
```

## canonical

```md
Cite @doi:10.1002/andp.19053221004 and @doi:10.1002/andp.19053221004.
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
          "text": "Cite "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "doi:10.1002/andp.19053221004"
            }
          ]
        },
        {
          "type": "Str",
          "text": " and "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "doi:10.1002/andp.19053221004"
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
