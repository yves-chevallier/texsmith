# Critic markup: insertion

Spec Appendix "PyMdownX compatibility profile", challenge C49: `{++x++}` is a
reviewer's insertion. It lowers to `Span{.critic}` around the `Underline` the
appendix names — the class tells a writer the mark is an annotation and not an
author's own underline — and the paged backends typeset it through the
`ts-critic` contract (`\tsins`, `#ts-ins`). The inner text is inline content,
so markup inside the annotation is markup. The critic spelling is canonical:
it is the only one, and it is class E under `pymdownx.critic`.

## input

```md
The release is {++almost **ready**++} now.
```

## canonical

```md
The release is {++almost **ready**++} now.
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
          "text": "The release is "
        },
        {
          "type": "Span",
          "content": [
            {
              "type": "Underline",
              "content": [
                {
                  "type": "Str",
                  "text": "almost "
                },
                {
                  "type": "Strong",
                  "content": [
                    {
                      "type": "Str",
                      "text": "ready"
                    }
                  ]
                }
              ]
            }
          ],
          "attrs": {
            "classes": [
              "critic"
            ]
          }
        },
        {
          "type": "Str",
          "text": " now."
        }
      ]
    }
  ]
}
```

## latex

```latex
The release is \tsins{almost \textbf{ready}} now.
```

## typst

```typst
The release is #ts-ins[almost *ready*] now.
```

## html

```html
<p>The release is <ins class="critic">almost <strong>ready</strong></ins> now.</p>
```
