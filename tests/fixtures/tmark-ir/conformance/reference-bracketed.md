# Bracketed reference

Spec §Ref, §Cite: `@[…]` as soon as an item has a space or there are several
items; Pandoc's item grammar (prefix, `-` to suppress the author, key,
suffix). Pandoc's `[@key, locator]` is accepted for import and never emitted.

## input

```md
As shown by @[see ein05, pp. 33-35; -AI2027, ch. 1].
```

```md
As shown by [see @ein05, pp. 33-35; -@AI2027, ch. 1].
```

## canonical

```md
As shown by @[see ein05, pp. 33-35; -AI2027, ch. 1].
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
          "text": "As shown by "
        },
        {
          "type": "Ref",
          "items": [
            {
              "prefix": "see",
              "key": "ein05",
              "suffix": "pp. 33-35"
            },
            {
              "suppress_author": true,
              "key": "AI2027",
              "suffix": "ch. 1"
            }
          ]
        },
        {
          "type": "Str",
          "text": "."
        }
      ]
    }
  ]
}
```
