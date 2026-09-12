# Critic markup: substitution

Spec Appendix "PyMdownX compatibility profile", challenge C49:
`{~~old~>new~~}` is the pair — a `Strikeout` and an `Underline`, in source
order, inside one `Span{.critic}`. The first `~>` splits the halves, which is
`pymdownx.critic`'s own non-greedy reading. LaTeX emits the two-argument
`\tssubst{old}{new}`, Typst `#ts-subst[old][new]`, the web the two elements.
A `{~~x~~}` without its `~>` is not a substitution and stays literal text.

## input

```md
Call it {~~colour~>color~~} everywhere.
```

## canonical

```md
Call it {~~colour~>color~~} everywhere.
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
          "text": "Call it "
        },
        {
          "type": "Span",
          "content": [
            {
              "type": "Strikeout",
              "content": [
                {
                  "type": "Str",
                  "text": "colour"
                }
              ]
            },
            {
              "type": "Underline",
              "content": [
                {
                  "type": "Str",
                  "text": "color"
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
          "text": " everywhere."
        }
      ]
    }
  ]
}
```

## latex

```latex
Call it \tssubst{colour}{color} everywhere.
```

## typst

```typst
Call it #ts-subst[colour][color] everywhere.
```

## html

```html
<p>Call it <del class="critic">colour</del><ins class="critic">color</ins> everywhere.</p>
```
