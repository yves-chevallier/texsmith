# Aside role

Spec §Aside (`MarginNote`). Zero-width node; `side=` is a layout hint; the
positional argument is sugar for `side`. `{margin}[…]` and its `{l}` suffix
are deprecated (Appendix Deprecation schedule).

## input

```md
Hooke's law {aside left}[linear only at small strain] holds.
```

```md
Hooke's law {aside side=left}[linear only at small strain] holds.
```

## canonical

```md
Hooke's law {aside side=left}[linear only at small strain] holds.
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
          "text": "Hooke's law "
        },
        {
          "type": "Aside",
          "content": [
            {
              "type": "Plain",
              "content": [
                {
                  "type": "Str",
                  "text": "linear only at small strain"
                }
              ]
            }
          ],
          "side": "left"
        },
        {
          "type": "Str",
          "text": " holds."
        }
      ]
    }
  ]
}
```

## latex

```latex
Hooke's law\marginnote[left]{linear only at small strain} holds.
```
