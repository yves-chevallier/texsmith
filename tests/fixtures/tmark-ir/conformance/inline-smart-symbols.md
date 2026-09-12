# Smart symbols and straight quotes

Spec Appendix "PyMdownX compatibility profile": `(c)`, `(tm)`, `-->`, `1/2`
are `Str` holding the character the symbol stands for, and a straight
double-quoted phrase is a `Quoted` (SmartyPants, §Quoted). Both are read
inside text runs only: a code span, a raw span, a destination and an
attribute value are never touched, and a backslash keeps the spelling
literal.

## input

```md
Copyright (c) 2025, tea (tm), reg (r), c/o Ada: 1/2 a cup, +/- 3, 4 =/= 5, a --> b.

He said "straight quotes", `"not in code"`, and \"not a quote\".
```

## canonical

```md
Copyright © 2025, tea ™, reg ®, ℅ Ada: ½ a cup, ± 3, 4 ≠ 5, a → b.

He said "straight quotes", `"not in code"`, and \"not a quote".
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
          "text": "Copyright © 2025, tea ™, reg ®, ℅ Ada: ½ a cup, ± 3, 4 ≠ 5, a → b."
        }
      ]
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "He said "
        },
        {
          "type": "Quoted",
          "kind": "double",
          "content": [
            {
              "type": "Str",
              "text": "straight quotes"
            }
          ]
        },
        {
          "type": "Str",
          "text": ", "
        },
        {
          "type": "Code",
          "text": "\"not in code\""
        },
        {
          "type": "Str",
          "text": ", and \"not a quote\"."
        }
      ]
    }
  ]
}
```

## latex

```latex
Copyright © 2025, tea ™, reg ®, ℅ Ada: ½ a cup, \(\pm\) 3, 4 \(\neq\) 5, a \(\rightarrow\) b.

He said \enquote{straight quotes}, \tscodeinline{"not in code"}, and "not a quote".
```
