# Recognised but unimplemented PyMdownX spellings

Spec Appendix "PyMdownX compatibility profile", design 05 (migration wave
1): wiki links and fancy list markers are milestone-5 work. Until then they
parse as literal text, as before, and each occurrence is reported as
`compat-unsupported` (a warning, so `tmark check --strict` fails) instead
of passing silently. Content tabs, progress bars, emoji and icon
shortcodes, `^^…^^` and `[TOC]` left this list with challenges C31–C42 and
critic markup with C49 (fixtures `critic-*`); each has its own fixture.

## input

```md
A word, a [[Wiki Page]].

a. first fancy item
```

## canonical

```md
A word, a [[Wiki Page]].

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
          "text": "A word, a [[Wiki Page]]."
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
compat-unsupported @ 1:11-1:24
compat-unsupported @ 3:1-3:20
```
