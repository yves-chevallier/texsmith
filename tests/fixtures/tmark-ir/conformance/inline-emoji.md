# Emoji shortcodes

Spec §Emoji and icon shortcodes: `:rocket:` is sugar for the character it
names in the `gemoji` table; the printer emits the character. A word that
is not in the table (`12:30:45`) stays literal.

## input

```md
Ship it :rocket: :smile: at 12:30:45.
```

```md
Ship it 🚀 😄 at 12:30:45.
```

## canonical

```md
Ship it 🚀 😄 at 12:30:45.
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "Ship it 🚀 😄 at 12:30:45."
        }
      ]
    }
  ]
}
```

