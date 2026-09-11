# Highlighted inline code

Spec §Inline text: `{code lang=py}[…]` canonical, `{code py}[…]` positional,
`` `#!py …` `` sugar. Plain code spans stay backticks.

## input

```md
Call `#!py print(1)` or {code py}[print(1)] but never `rm -rf`.
```

```md
Call {code lang=py}[print(1)] or {code lang=py}[print(1)] but never `rm -rf`.
```

## canonical

```md
Call {code lang=py}[print(1)] or {code lang=py}[print(1)] but never `rm -rf`.
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
          "text": "Call "
        },
        {
          "type": "Code",
          "text": "print(1)",
          "lang": "py"
        },
        {
          "type": "Str",
          "text": " or "
        },
        {
          "type": "Code",
          "text": "print(1)",
          "lang": "py"
        },
        {
          "type": "Str",
          "text": " but never "
        },
        {
          "type": "Code",
          "text": "rm -rf"
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
