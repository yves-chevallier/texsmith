# Math

Spec §Math (inline), §Math (display): `$…$` and `$$ … $$ {#eq:x}` are
canonical; `\(…\)` and `\[…\]` are the LaTeX-habit compatibility layer.

## input

```md
Inline \(a^2\) and $b^2$.

\[
a^2 + b^2 = c^2
\]

$$
e = mc^2
$$ {#eq:einstein}
```

## canonical

```md
Inline $a^2$ and $b^2$.

$$
a^2 + b^2 = c^2
$$

$$
e = mc^2
$$ {#eq:einstein}
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
          "text": "Inline "
        },
        {
          "type": "Math",
          "text": "a^2"
        },
        {
          "type": "Str",
          "text": " and "
        },
        {
          "type": "Math",
          "text": "b^2"
        },
        {
          "type": "Str",
          "text": "."
        }
      ]
    },
    {
      "type": "MathBlock",
      "text": "a^2 + b^2 = c^2"
    },
    {
      "type": "MathBlock",
      "text": "e = mc^2",
      "attrs": {
        "id": "eq:einstein"
      }
    }
  ]
}
```
