# Table payload that is not a mapping

Spec §Table rung 5, design 05 `table-yaml`: a `yaml table` fence whose
payload is not YAML or not a mapping stays a code block with its node word
and prints back as typed.

## input

````md
```yaml table
- not
- a mapping
```
````
## canonical

````md
```yaml table
- not
- a mapping
```
````

## ir

```json
{
  "blocks": [
    {
      "type": "CodeBlock",
      "text": "- not\n- a mapping",
      "lang": "yaml table"
    }
  ]
}
```

## diagnostics

```text
table-yaml @ 1:1-4:4
```
