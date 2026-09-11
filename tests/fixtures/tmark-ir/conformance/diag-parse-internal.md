# Internal tokenizer failure: the document stays a document

AGENTS.md: "parsing never fails". markdown-rs 1.0.0 panics in `to_mdast`
on an unclosed fence inside a list item followed by a list of another
kind (`- ```h` then `1. i`; `to_html` does not). Until the vendored
tokenizer is fixed, the parser catches the failure, keeps the text as one
paragraph and reports `parse-internal` (an error: the printer refuses to
format such a file).

## input

````md
- ```h
1. i
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
          "text": "- ```h\n1. i\n"
        }
      ]
    }
  ]
}
```

## diagnostics

```text
parse-internal @ 1:1-3:1
```
