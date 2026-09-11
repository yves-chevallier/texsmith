# Counter prefixes: undeclared, and on the wrong host

Spec §CounterItem ("An undeclared prefix warns") and §Anchor ("when a
prefix is present it must agree with the host, and a mismatch is linted").

## input

```md
#(rq:one) A requirement with an undeclared series.

![Trace](trace.png){#tbl:trace}
```

## canonical

```md
{counter}(rq:one) A requirement with an undeclared series.

![Trace](trace.png){#tbl:trace}
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "CounterItem",
          "prefix": "rq",
          "key": "one"
        },
        {
          "type": "Str",
          "text": " A requirement with an undeclared series."
        }
      ]
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Image",
          "src": "trace.png",
          "alt": [
            {
              "type": "Str",
              "text": "Trace"
            }
          ],
          "attrs": {
            "id": "tbl:trace"
          }
        }
      ]
    }
  ]
}
```

## resolution

```text
prefix-unknown @ 1:1-1:10
prefix-host-mismatch @ 3:1-3:32
```
