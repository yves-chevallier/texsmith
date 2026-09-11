# Duplicate label

Spec §Counters: "Duplicates and dangling references warn loudly."

## input

```md
## A {#sec:a}

## B {#sec:a}
```

## canonical

```md
## A {#sec:a}

## B {#sec:a}
```

## ir

```json
{
  "blocks": [
    {
      "type": "Header",
      "level": 2,
      "content": [
        {
          "type": "Str",
          "text": "A"
        }
      ],
      "attrs": {
        "id": "sec:a"
      }
    },
    {
      "type": "Header",
      "level": 2,
      "content": [
        {
          "type": "Str",
          "text": "B"
        }
      ],
      "attrs": {
        "id": "sec:a"
      }
    }
  ]
}
```

## resolution

```text
label-duplicate @ 3:1-3:14
```
