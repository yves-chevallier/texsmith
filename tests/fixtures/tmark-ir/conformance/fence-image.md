# Generated image

Spec §Image, Figure: `python image` executes and embeds; a bare `mermaid`
fence is an image, `mermaid code` a listing.

## input

````md
```python image include="plot.py"
plt.plot([1, 2, 4, 8])
```

```mermaid
flowchart LR
  A --> B
```

```mermaid code
flowchart LR
  A --> B
```
````

## canonical

````md
```python image include="plot.py"
plt.plot([1, 2, 4, 8])
```

```mermaid image
flowchart LR
  A --> B
```

```mermaid code
flowchart LR
  A --> B
```
````

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Image",
          "attrs": {
            "kv": [
              [
                "generate",
                "python"
              ],
              [
                "code",
                "plt.plot([1, 2, 4, 8])"
              ],
              [
                "include",
                "plot.py"
              ]
            ]
          }
        }
      ]
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Image",
          "attrs": {
            "kv": [
              [
                "generate",
                "mermaid"
              ],
              [
                "code",
                "flowchart LR\n  A --> B"
              ]
            ]
          }
        }
      ]
    },
    {
      "type": "CodeBlock",
      "text": "flowchart LR\n  A --> B",
      "lang": "mermaid"
    }
  ]
}
```
