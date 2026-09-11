# Prose lints

`tmark lint` (spec §Tooling roadmap): hard-coded numbers and position
words are references in disguise.

## input

```md
Figure 3 shows the trace; see the table below and the notes above.
```

## canonical

```md
Figure 3 shows the trace; see the table below and the notes above.
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
          "text": "Figure 3 shows the trace; see the table below and the notes above."
        }
      ]
    }
  ]
}
```

## resolution

```text
hardcoded-number @ 1:1-1:9
position-word @ 1:41-1:46
position-word @ 1:61-1:66
```
