# HTML kept as typed

Spec §Raw passthrough: inline and block HTML other than comments is
`RawInline` / `RawBlock` with `format=html`, class C, printed as typed;
paged writers drop it (the span text survives, `<br>` prints nothing).

## input

```md
Inline <span class="x">text</span> and <br> here.

<div class="note">
Raw block.
</div>
```

## canonical

```md
Inline <span class="x">text</span> and <br> here.

<div class="note">
Raw block.
</div>
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
          "type": "RawInline",
          "format": "html",
          "text": "<span class=\"x\">"
        },
        {
          "type": "Str",
          "text": "text"
        },
        {
          "type": "RawInline",
          "format": "html",
          "text": "</span>"
        },
        {
          "type": "Str",
          "text": " and "
        },
        {
          "type": "RawInline",
          "format": "html",
          "text": "<br>"
        },
        {
          "type": "Str",
          "text": " here."
        }
      ]
    },
    {
      "type": "RawBlock",
      "format": "html",
      "text": "<div class=\"note\">\nRaw block.\n</div>"
    }
  ]
}
```

