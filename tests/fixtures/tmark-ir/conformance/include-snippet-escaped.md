# Snippet marker disabled by `;`

Spec §Includes and Appendix "Deprecation schedule": `pymdownx.snippets`
escapes its own marker with a `;` before it. An escaped line includes
nothing and reaches the document as the text it spells, less one `;`; no
diagnostic fires, since nothing is deprecated about writing the marker.

The canonical spelling of the text is whatever escapes it for the reader
that would otherwise take it: a backslash in a paragraph, and in a fence
body — which has no backslash escape — the `;` itself.

## input

````md
;---8<--- "chapters/boot.md"

```python
;--8<-- "hanoi.py"
```
````

## canonical

````md
\---8<--- "chapters/boot.md"

```python
;--8<-- "hanoi.py"
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
          "type": "Str",
          "text": "---8<--- "
        },
        {
          "type": "Quoted",
          "kind": "double",
          "content": [
            {
              "type": "Str",
              "text": "chapters/boot.md"
            }
          ]
        }
      ]
    },
    {
      "type": "CodeBlock",
      "text": "--8<-- \"hanoi.py\"",
      "lang": "python"
    }
  ]
}
```
