# Critic markup: highlight

Spec Appendix "PyMdownX compatibility profile", challenge C49: `{==x==}` is
critic's spelling of `pymdownx.mark`. It is not an annotation — the
`ts-critic` contract defines no macro for it and the legacy renderer routed
both spellings to the one highlight partial — so it lowers to the plain
`Highlight` that `==x==` produces, prints as the `{mark}` role and reaches
`\tsmark` of `ts-typesetting`.

## input

```md
Keep {==this sentence==} for the summary.
```

```md
Keep ==this sentence== for the summary.
```

## canonical

```md
Keep {mark}[this sentence] for the summary.
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
          "text": "Keep "
        },
        {
          "type": "Highlight",
          "content": [
            {
              "type": "Str",
              "text": "this sentence"
            }
          ]
        },
        {
          "type": "Str",
          "text": " for the summary."
        }
      ]
    }
  ]
}
```

## latex

```latex
Keep \tsmark{this sentence} for the summary.
```

## typst

```typst
Keep #highlight[this sentence] for the summary.
```

## html

```html
<p>Keep <mark>this sentence</mark> for the summary.</p>
```
