# Emoji and icons

Two colon-delimited shortcodes look alike and behave differently, because one
names a **character** and the other names an **SVG that only a website has**.

## Emoji

`:smile:` is sugar for the character it names: the parser replaces it with the
character, and that is what reaches every backend.

```md
Ship it :rocket: :smile: at 12:30:45.
```

renders as

> Ship it 🚀 😄 at 12:30:45.

The name table is GitHub's — the `gemoji` short names, which `pymdownx.emoji`
ships as one of its indexes. A colon-delimited word that is **not** in the
table is literal text with no diagnostic, which is what keeps `12:30:45` and
`a:b:c` safe. Nothing fires inside code.

Class E, and GitHub renders the shortcodes too, so the source stays readable
wherever it is pasted. How an emoji is *set* in print — a colour font, a
monochrome one, an image — is the template's business, not syntax.

## Material icons

An icon shortcode names an SVG of the MkDocs Material theme, which no print
backend and no icon-less site can honour. Four set prefixes are recognised:

```md
Click :material-cog: Settings, :fontawesome-solid-check: to confirm,
:octicons-tag-16: for a release, :simple-github: for the repository.
```

Such a shortcode lowers to a **web-only span** holding the shortcode as its
text. The `media=web` rule then removes it from print — the spaces around it
collapse, as for any [zero-width node](extra.md#three-universal-attributes) —
and the HTML writer emits `<span class="icon">:material-cog:</span>` for the
site's stylesheet or plugin to replace.

The shortcode is its own canonical spelling: the printer writes such a span
back as the shortcode, so the round-trip is exact.

!!! warning "Icons do not reach the PDF"
    `tmark check` raises the hint `icon-web-only` once per shortcode, so an
    author writing for print knows the icon is not there. Icons are decoration;
    a symbol that must reach print is an **emoji** or an **image**.

| Construct | Canonical | Print | Web | Class |
| --------- | --------- | ----- | --- | ----- |
| `:smile:` | the character | the character | the character | E |
| `:material-cog:` | the shortcode | dropped | `<span class="icon">` | D |

See also [Smart symbols and quotes](symbols.md) for the substitutions that run
on ASCII punctuation.
