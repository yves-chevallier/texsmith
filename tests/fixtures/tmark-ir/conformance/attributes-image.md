# Image attributes and figure caption

Spec §Image, Figure, §Caption: attributes attach to the image right after
it; the caption line follows the image paragraph.

## input

```md
![Trace of the boot](trace.png){width=60% #fig:trace}

Figure: The watchdog fires **twice**. {#fig:plot}
```

## canonical

```md
![Trace of the boot](trace.png){#fig:trace width=60%}

Figure: The watchdog fires **twice**. {#fig:plot}
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Image",
          "src": "trace.png",
          "alt": [
            {
              "type": "Str",
              "text": "Trace of the boot"
            }
          ],
          "attrs": {
            "id": "fig:trace",
            "kv": [
              [
                "width",
                "60%"
              ]
            ]
          }
        }
      ]
    },
    {
      "type": "Caption",
      "kind": "figure",
      "content": [
        {
          "type": "Str",
          "text": "The watchdog fires "
        },
        {
          "type": "Strong",
          "content": [
            {
              "type": "Str",
              "text": "twice"
            }
          ]
        },
        {
          "type": "Str",
          "text": "."
        }
      ],
      "attrs": {
        "id": "fig:plot"
      }
    }
  ]
}
```
