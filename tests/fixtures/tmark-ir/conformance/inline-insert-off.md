# Caret insert with the feature off

Spec §Inline text: with `inline.insert` off (the default) `^^x^^` is
literal text and lint hints `feature-off`. The printer escapes the carets
(`^x^` is superscript sugar); the escaped spelling is the author's literal
text and gets no hint.

## input

```md
Now ^^inserted^^ text.
```

## canonical

```md
Now \^\^inserted\^\^ text.
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
          "text": "Now ^^inserted^^ text."
        }
      ]
    }
  ]
}
```

## resolution

```text
feature-off @ 1:5-1:17
```
