# Divider

Spec §HorizontalRule: `---` is a `HorizontalRule`; the LaTeX writer emits
`\tsdivider`, the Typst writer `#ts-divider()` (a page break by default,
redefinable by the template), the HTML writer `<hr>`.

## input

```md
First page.

---

Second page.
```

## canonical

```md
First page.

---

Second page.
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
          "text": "First page."
        }
      ]
    },
    {
      "type": "HorizontalRule"
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "Second page."
        }
      ]
    }
  ]
}
```

