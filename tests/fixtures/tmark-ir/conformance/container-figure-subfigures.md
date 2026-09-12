# Figure container, sub-figures

Spec §Image, Figure: the images of a `::: figure` are sub-figures. The
container takes one number of the `fig` series and each image takes that
number with a letter, so `@fig:left` reads "figure 2a" while a plain
figure before the container keeps number 1.

## input

```md
![Trace](trace.svg){#fig:trace}

Figure: A trace.

::: figure {cols=2}
![Left](l.svg){#fig:left}
![Right](r.svg){#fig:right}
:::

Figure: Two views. {#fig:views}

See @fig:trace, @fig:views and @fig:left.
```

## canonical

```md
![Trace](trace.svg){#fig:trace}

Figure: A trace.

::: figure {cols=2}
![Left](l.svg){#fig:left}
![Right](r.svg){#fig:right}
:::

Figure: Two views. {#fig:views}

See @fig:trace, @fig:views and @fig:left.
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Image",
          "src": "trace.svg",
          "alt": [
            {
              "type": "Str",
              "text": "Trace"
            }
          ],
          "attrs": {
            "id": "fig:trace"
          }
        }
      ]
    },
    {
      "type": "Caption",
      "kind": "figure",
      "content": [
        {
          "type": "Str",
          "text": "A trace."
        }
      ]
    },
    {
      "type": "Figure",
      "content": [
        {
          "type": "Para",
          "content": [
            {
              "type": "Image",
              "src": "l.svg",
              "alt": [
                {
                  "type": "Str",
                  "text": "Left"
                }
              ],
              "attrs": {
                "id": "fig:left"
              }
            },
            {
              "type": "SoftBreak"
            },
            {
              "type": "Image",
              "src": "r.svg",
              "alt": [
                {
                  "type": "Str",
                  "text": "Right"
                }
              ],
              "attrs": {
                "id": "fig:right"
              }
            }
          ]
        }
      ],
      "attrs": {
        "kv": [
          [
            "cols",
            "2"
          ]
        ]
      }
    },
    {
      "type": "Caption",
      "kind": "figure",
      "content": [
        {
          "type": "Str",
          "text": "Two views."
        }
      ],
      "attrs": {
        "id": "fig:views"
      }
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "See "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "fig:trace"
            }
          ]
        },
        {
          "type": "Str",
          "text": ", "
        },
        {
          "type": "Ref",
          "items": [
            {
              "key": "fig:views"
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
              "key": "fig:left"
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
