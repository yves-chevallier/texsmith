# Deprecated front-matter keys

Spec Appendix "Deprecation schedule": the top-level groups `bibliography`,
`crossrefs` (→ `press.sources`) and `counters`, `admonitions`, `glossary`,
`acronyms` (→ `press.declare`), and `press.callout_style` /
`press.admonition_style` (→ `press.callouts.style`), are read at their old
place with a `deprecated-frontmatter-key` diagnostic each. The diagnostic
carries one fix that moves every such key (a line edit of the YAML island,
`tmark_ir::yaml_edit`); `tmark fmt` copies the front matter as is, so the
canonical text below is the input. A bare string under `authors` is a
name (C9).

## input

```md
---
title: Notes
authors: [TeXSmith]
counters:
  fw:
    name: Finding
press:
  admonition_style: classic
---

Text.
```

## canonical

```md
---
title: Notes
authors: [TeXSmith]
counters:
  fw:
    name: Finding
press:
  admonition_style: classic
---

Text.
```

## ir

```json
{
  "front_matter": {
    "raw": "---\ntitle: Notes\nauthors: [TeXSmith]\ncounters:\n  fw:\n    name: Finding\npress:\n  admonition_style: classic\n---",
    "keys": {
      "title": "Notes",
      "authors": [
        {
          "name": "TeXSmith"
        }
      ],
      "press": {
        "declare": {
          "counters": {
            "fw": {
              "name": "Finding"
            }
          }
        }
      }
    },
    "extra": {
      "press": {
        "callouts": {
          "style": "classic"
        }
      }
    },
    "deprecated": [
      "counters",
      "press.admonition_style"
    ]
  },
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "Text."
        }
      ]
    }
  ]
}
```

## diagnostics

```text
deprecated-frontmatter-key @ 1:1-9:4
deprecated-frontmatter-key @ 1:1-9:4
```
