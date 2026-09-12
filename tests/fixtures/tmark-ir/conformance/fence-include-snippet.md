# Listing whose body is a snippet line

Spec §Listing (`include="file"` on the info string) and Appendix
"Deprecation schedule" (`--8<-- "file"`): a fence holding only a PyMdownX
snippet line is the listing of that file, `include="file"` on the info
string and an empty body. The fix rewrites the fence. The marker is
`-{2,}8<-{2,}`, as in a paragraph: any dash count of two or more on each
side, the two sides free to differ. A body that *shows* a snippet line
instead of including it is escaped with `;` (`include-snippet-escaped`).

## input

````md
```python
--8<-- "hanoi.py"
```
````

````md
```python
---8<--- "hanoi.py"
```
````

````md
```python
--8<---- "hanoi.py"
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
