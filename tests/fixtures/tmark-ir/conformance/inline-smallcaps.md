# Small caps

Spec §Inline text, deviation X1: `__x__` is small caps, not bold. The role
`{sc}` is canonical.

## input

```md
Small caps __on the label__ here.
```

```md
Small caps {sc}[on the label] here.
```

## canonical

```md
Small caps {sc}[on the label] here.
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
          "text": "Small caps "
        },
        {
          "type": "SmallCaps",
          "content": [
            {
              "type": "Str",
              "text": "on the label"
            }
          ]
        },
        {
          "type": "Str",
          "text": " here."
        }
      ]
    }
  ]
}
```

## latex

```latex
Small caps \textsc{on the label} here.
```

## typst

```typst
Small caps #smallcaps[on the label] here.
```

## html

```html
<p>Small caps <span class="smallcaps">on the label</span> here.</p>
```
