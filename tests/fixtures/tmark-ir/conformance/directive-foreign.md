# Foreign directives

Spec §Foreign directive: `[TOC]` alone in a paragraph and a dotted `:::`
line with its indented continuation (mkdocstrings) are `RawBlock` with
`format=markdown`, kept verbatim by the printer, emitted by no other writer;
the dotted form closes at the first dedent and raises no container
diagnostic, only the lint hint `directive-foreign` (C42 for `[TOC]`).

## input

```md
[TOC]

::: texsmith.core.config
    options:
      members: true

Next paragraph.
```

## canonical

```md
[TOC]

::: texsmith.core.config
    options:
      members: true

Next paragraph.
```

## ir

```json
{
  "blocks": [
    {
      "type": "RawBlock",
      "format": "markdown",
      "text": "[TOC]"
    },
    {
      "type": "RawBlock",
      "format": "markdown",
      "text": "::: texsmith.core.config\n    options:\n      members: true"
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "Next paragraph."
        }
      ]
    }
  ]
}
```

## resolution

```text
directive-foreign @ 3:1-5:20
```
