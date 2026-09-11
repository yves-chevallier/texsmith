# Moustaches

Spec §Front matter: `{{ key }}` and `{{ press.template }}` are substitution
variables; never inside code.

## input

```md
Built with {{title}} as {{ press.template }} but not `{{ code }}`.
```

## canonical

```md
Built with {{ title }} as {{ press.template }} but not `{{ code }}`.
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
          "text": "Built with "
        },
        {
          "type": "Var",
          "path": [
            "title"
          ]
        },
        {
          "type": "Str",
          "text": " as "
        },
        {
          "type": "Var",
          "path": [
            "press",
            "template"
          ]
        },
        {
          "type": "Str",
          "text": " but not "
        },
        {
          "type": "Code",
          "text": "{{ code }}"
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
