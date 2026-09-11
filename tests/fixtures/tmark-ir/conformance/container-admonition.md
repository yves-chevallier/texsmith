# Admonition container

Spec §Admonition: `:::` is canonical; `!!!` is accepted sugar (class E). The
title is an attribute.

## input

```md
::: warning {title="LaTeX toolchain"}
Install TeX Live before `texsmith --build`.
:::
```

```md
!!! warning "LaTeX toolchain"
    Install TeX Live before `texsmith --build`.
```

## canonical

```md
::: warning {title="LaTeX toolchain"}
Install TeX Live before `texsmith --build`.
:::
```

## ir

```json
{
  "blocks": [
    {
      "type": "Admonition",
      "kind": "warning",
      "title": [
        {
          "type": "Str",
          "text": "LaTeX toolchain"
        }
      ],
      "content": [
        {
          "type": "Para",
          "content": [
            {
              "type": "Str",
              "text": "Install TeX Live before "
            },
            {
              "type": "Code",
              "text": "texsmith --build"
            },
            {
              "type": "Str",
              "text": "."
            }
          ]
        }
      ]
    }
  ]
}
```
