# Snippet marker, any dash count

Spec §Includes and Appendix "Deprecation schedule": the PyMdownX snippet
marker is `-{2,}8<-{2,}` — two or more dashes on each side, and the two
sides need not match — so `--8<--`, `---8<---` and `--8<----` are one
spelling. Every one of them is the deprecated sugar for `{include}(file)`.

## input

```md
---8<--- "chapters/boot.md"
```

```md
--8<-- "chapters/boot.md"
```

```md
--8<---- "chapters/boot.md"
```

```md
-----8<----- "chapters/boot.md"
```

## canonical

```md
{include}(chapters/boot.md)
```

## ir

```json
{
  "blocks": [
    {
      "type": "Include",
      "path": "chapters/boot.md"
    }
  ]
}
```

## diagnostics

```text
deprecated @ 1:1-1:28
```
