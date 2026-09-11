# An attribute list with nothing to attach to

Spec §Attributes: a list needs a host element. At the end of a paragraph
of plain text it is literal text (`attr-no-host`), merged with the text
before it like any other literal fallback; the printer escapes the brace
so that the diagnostic does not come back (and only the `]` of the
brackets: an opening `[` fires nothing on its own).

## input

```md
\[x\]{#id}
```

## canonical

```md
[x\]\{#id}
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
          "text": "[x]{#id}"
        }
      ]
    }
  ]
}
```

## diagnostics

```text
attr-no-host @ 1:6-1:11
```
