# Attribute list with the Python-Markdown colon

Spec §Attributes: `{: #id .cls}` (Python-Markdown `attr_list`) is accepted
on every host and deprecated; the printer drops the colon.

## input

```md
## Boot {: #sec:boot .draft}
```

```md
## Boot {#sec:boot .draft}
```

## canonical

```md
## Boot {#sec:boot .draft}
```

## ir

```json
{
  "blocks": [
    {
      "type": "Header",
      "level": 2,
      "content": [
        {
          "type": "Str",
          "text": "Boot"
        }
      ],
      "attrs": {
        "id": "sec:boot",
        "classes": [
          "draft"
        ]
      }
    }
  ]
}
```

## diagnostics

```text
deprecated @ 1:9-1:29
```
