# Raw passthrough

Spec §Raw passthrough: `{raw backend}(…)` inline, `<backend> raw` fence;
the deprecated `{latex}[…]` role normalises to the raw role.

## input

````md
A page break {raw latex}(\clearpage) here.

```latex raw
\vspace{1cm}
```
````

## canonical

````md
A page break {raw latex}(\clearpage) here.

```latex raw
\vspace{1cm}
```
````

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "A page break "
        },
        {
          "type": "RawInline",
          "format": "latex",
          "text": "\\clearpage"
        },
        {
          "type": "Str",
          "text": " here."
        }
      ]
    },
    {
      "type": "RawBlock",
      "format": "latex",
      "text": "\\vspace{1cm}"
    }
  ]
}
```
