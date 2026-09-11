# Index entries

Spec §IndexEntry: `{index}[…]` with up to three bracket groups is
canonical; `#[…]` is sugar; `#[**term**]` is lossy sugar for `main=true`
(design C5).

## input

```md
Bytes #[endianness] and #[byte order][endianness] and #[**chocolate**].
```

```md
Bytes {index}[endianness] and {index}[byte order][endianness] and {index main=true}[chocolate].
```

## canonical

```md
Bytes {index}[endianness] and {index}[byte order][endianness] and {index main=true}[chocolate].
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
          "text": "Bytes "
        },
        {
          "type": "IndexEntry",
          "path": [
            [
              {
                "type": "Str",
                "text": "endianness"
              }
            ]
          ]
        },
        {
          "type": "Str",
          "text": " and "
        },
        {
          "type": "IndexEntry",
          "path": [
            [
              {
                "type": "Str",
                "text": "byte order"
              }
            ],
            [
              {
                "type": "Str",
                "text": "endianness"
              }
            ]
          ]
        },
        {
          "type": "Str",
          "text": " and "
        },
        {
          "type": "IndexEntry",
          "path": [
            [
              {
                "type": "Str",
                "text": "chocolate"
              }
            ]
          ],
          "main": true
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
