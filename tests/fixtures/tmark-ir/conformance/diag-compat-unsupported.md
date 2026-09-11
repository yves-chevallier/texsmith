# Recognised but unimplemented PyMdownX spellings

Spec Appendix "PyMdownX compatibility profile", design 05 (migration wave
1): content tabs, critic markup, progress bars, wiki links, emoji and icon
shortcodes, `^^…^^` without `inline.insert`, fancy list markers and `[TOC]`
are milestone-5 work. Until then they parse as literal text, as before,
and each occurrence is reported as `compat-unsupported` (a warning, so
`tmark check --strict` fails) instead of passing silently. The printer
escapes what could be misread (`\=\=\=`, `\{--`, `\]{`, `\^\^`).

## input

```md
=== "Windows"

A {--deleted--} word, a bar [=45% "Review"]{: .thin}, a [[Wiki Page]],
an emoji :smile: and an icon :material-home:, then ^^inserted^^ text.

a. first fancy item

[TOC]
```

## canonical

```md
\=\=\= "Windows"

A \{--deleted--} word, a bar [=45% "Review"\]{: .thin}, a [[Wiki Page]],
an emoji :smile: and an icon :material-home:, then \^\^inserted\^\^ text.

a. first fancy item

[TOC]
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
          "text": "=== \"Windows\""
        }
      ]
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "A {--deleted--} word, a bar [=45% \"Review\"]{: .thin}, a [[Wiki Page]],"
        },
        {
          "type": "SoftBreak"
        },
        {
          "type": "Str",
          "text": "an emoji :smile: and an icon :material-home:, then ^^inserted^^ text."
        }
      ]
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "a. first fancy item"
        }
      ]
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "[TOC]"
        }
      ]
    }
  ]
}
```

## diagnostics

```text
compat-unsupported @ 1:1-1:14
compat-unsupported @ 3:3-3:16
compat-unsupported @ 3:29-3:44
compat-unsupported @ 3:57-3:70
compat-unsupported @ 4:10-4:17
compat-unsupported @ 4:30-4:45
compat-unsupported @ 4:52-4:64
compat-unsupported @ 6:1-6:20
compat-unsupported @ 8:1-8:6
```
