# Includes

Spec §Includes: `{include}(path)` alone on its line; the PyMdownX snippet
is deprecated sugar.

## input

```md
--8<-- "chapters/boot.md"

{include base=chapters}(chapters/setup.md)
```

## canonical

```md
{include}(chapters/boot.md)

{include base=chapters}(chapters/setup.md)
```

## ir

```json
{
  "blocks": [
    {
      "type": "Include",
      "path": "chapters/boot.md"
    },
    {
      "type": "Include",
      "path": "chapters/setup.md",
      "base": "chapters"
    }
  ]
}
```

## diagnostics

```text
deprecated @ 1:1-1:26
```
