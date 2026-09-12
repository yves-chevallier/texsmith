# Attributes

Attributes are the first of TMark's [four families](index.md#four-syntactic-families):
they decorate an element that already exists, and they are written in braces
**after** it.

```md
# Header 1 {#sec:header .class1 key="value"}

![Alt text](image.jpg){#fig:img .responsive width="300"}

[A phrase with an anchor]{#claim:one}

[this taylor]{lang=en}

| set on the cell | set on the emphasis |
| --------------- | ------------------- |
| [*a*]{.foo}     | *b*{.foo}           |
```

Grammar: `{`, then any number of `#id`, `.class` and `key=value` items separated
by spaces, then `}`. Values containing spaces are double-quoted, and inside a
quoted value `\"` stands for a quote.

There are **no bare-word attributes**: write `{collapsed=true}`, not
`{collapsed}`. That restriction is what makes attributes and roles disjoint
grammars — an attribute list begins with `#`, `.` or `key=`, a role head with a
bare identifier — so a brace group that is neither (`{foo}` in running text)
stays literal text.

## Attributes need a host

Headings, images, links, fenced blocks, tables, caption lines and display math
are hosts. A brace group with nothing to attach to is literal text and raises
`attributes-no-host`.

Where you want attributes on a piece of running text, use an **anonymous span**,
Pandoc-style: `[text]{attrs}`. The span exists for properties of a piece of text
rather than a new kind of node — an anchor on a phrase, the language of a
quotation, a media restriction.

## Three universal attributes

`#id`
:   An anchor. `@id` then refers to it, and the host decides which counter the
    anchor joins: a heading is a section, a `Table:` line is a table, an image
    is a figure.

`lang=`
:   The language of the element, for hyphenation, quotes and typographic
    spacing. The document default is the root `lang:` key.

`media=`
:   Where the element is rendered: `all` (default), `print` or `web`. A word, a
    paragraph, a code block, a callout or a video restricted to one medium is
    the escape hatch when symmetry is impossible, and it replaces mirrored
    `latex raw` / `html raw` blocks.

```md
The demo is [online only]{media=web}, and here is the [printed table]{media=print}.
```

!!! note "`[](){#id}` is deprecated"
    An empty link hugging an attribute list — the MkDocs/autorefs anchor idiom
    — is the same anchor written the long way. An empty link is no link, so
    `[](){#id}` reads as the span `[]{#id}`, which is the canonical spelling.
    The older form used to leave a `\url{}` and a dangling `\hyperref` behind.
    `tmark lint --fix` rewrites it.

!!! note "`{: .class}` is deprecated"
    Python-Markdown's `attr_list` puts a colon right after the brace
    (`{: .thin #id}`). That spelling is accepted on every host as sugar, with a
    deprecation warning, and the printer drops the colon.
    `tmark lint --fix` rewrites it; see
    [Migrating to TMark](../guide/migration.md).
