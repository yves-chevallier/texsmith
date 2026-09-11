# Listing with options

Spec §CodeBlock, listing: options in the info string, a `Listing:` caption
line after the block.

## input

````md
```python title="bubble_sort.py" linenums="1" hl_lines="2-3"
def bubble_sort(items): ...
```

Listing: Bubble sort, naive version. {#lst:bubble}
````

## canonical

````md
```python title="bubble_sort.py" linenums="1" hl_lines="2-3"
def bubble_sort(items): ...
```

Listing: Bubble sort, naive version. {#lst:bubble}
````

## ir

```json
{
  "blocks": [
    {
      "type": "CodeBlock",
      "text": "def bubble_sort(items): ...",
      "lang": "python",
      "options": {
        "kv": [
          [
            "title",
            "bubble_sort.py"
          ],
          [
            "linenums",
            "1"
          ],
          [
            "hl_lines",
            "2-3"
          ]
        ]
      }
    },
    {
      "type": "Caption",
      "kind": "listing",
      "content": [
        {
          "type": "Str",
          "text": "Bubble sort, naive version."
        }
      ],
      "attrs": {
        "id": "lst:bubble"
      }
    }
  ]
}
```
