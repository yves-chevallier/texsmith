# Recognised but unimplemented PyMdownX spellings

Spec Appendix "PyMdownX compatibility profile", design 05 (migration wave
1): critic markup, wiki links and fancy list markers are milestone-5 work.
Until then they parse as literal text, as before, and each occurrence is
reported as `compat-unsupported` (a warning, so `tmark check --strict`
fails) instead of passing silently. The printer escapes what could be
misread (`\{--`). Content tabs, progress bars, emoji and icon shortcodes,
`^^…^^` and `[TOC]` left this list with challenges C31–C42: each has its
own fixture.

## input

```md
A {--deleted--} word, a [[Wiki Page]].

a. first fancy item
```

## canonical

```md
A \{--deleted--} word, a [[Wiki Page]].

a. first fancy item
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
          "text": "A {--deleted--} word, a [[Wiki Page]]."
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
    }
  ]
}
```

## diagnostics

```text
compat-unsupported @ 1:3-1:16
compat-unsupported @ 1:25-1:38
compat-unsupported @ 3:1-3:20
```
