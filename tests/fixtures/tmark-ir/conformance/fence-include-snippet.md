# Listing whose body is a snippet line

Spec §Listing (`include="file"` on the info string) and Appendix
"Deprecation schedule" (`--8<-- "file"`): a fence holding only a PyMdownX
snippet line is the listing of that file, `include="file"` on the info
string and an empty body. The fix rewrites the fence.

## input

````md
```python
--8<-- "hanoi.py"
```
````

## canonical

````md
```python include="hanoi.py"
```
````

## ir

```json
{
  "blocks": [
    {
      "type": "CodeBlock",
      "lang": "python",
      "options": {
        "kv": [
          [
            "include",
            "hanoi.py"
          ]
        ]
      }
    }
  ]
}
```

## diagnostics

```text
deprecated @ 1:1-3:4
```
