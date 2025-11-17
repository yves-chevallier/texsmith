# Admonitions

Admonitions are special blocks that highlight important information, such as notes, warnings, tips, and more. They are created using the `admonition` extension in Python-Markdown.

Here the are two ways to create admonitions in your Markdown documents, either the standard style:

```markdown
!!! note "This is a Note"
    Any number of other indented markdown elements.

    This is the second paragraph.
```

!!! note "This is a Note"
    Any number of other indented markdown elements.

    This is the second paragraph.

Or de foldable style:

```markdown
??? note "This is a Note"
    Any number of other indented markdown elements.

    This is the second paragraph.
```

??? note "This is a Note"
    Any number of other indented markdown elements.

    This is the second paragraph.

## LaTeX Rendering

Admonitions can be rendered in LaTeX using the `tcolorbox` package. TeXSmith automatically converts admonitions into appropriate LaTeX environments.
Template authors can customize the appearance of admonitions by modifying the LaTeX preamble or the template slots.

Builtin templates like `article` and `book` already include basic styling for admonitions providing a consistent look and feel across documents.
Set the `callout_style` attribute (via front matter or CLI `--attribute callout_style=<style>`) to switch among the bundled palettes:

```yaml
---
press:
  callout_style: classic  # fancy | classic | minimal
---
```

- `fancy` (default): colored headings with icons.
- `classic`: black-and-white layout with a bold left rule.
- `minimal`: subtle border, rounded corners, and no icons.

=== "Fancy Admonitions"

    [![Fancy Admonitions](../assets/examples/fancy-admonition.png)](../assets/examples/fancy-admonition.pdf)

=== "Classic and Minimal Admonitions"

    [![Classic Admonitions](../assets/examples/classic-admonition.png)](../assets/examples/classic-admonition.pdf)

=== "Minimal Admonitions"

    [![Minimal Admonitions](../assets/examples/minimal-admonition.png)](../assets/examples/minimal-admonition.pdf)

## Builtin Admonition Types

The following admonition types are built into the `admonition` extension:

!!! note
    A Note

!!! tip
    A Tip

!!! warning
    A Warning

!!! important
    An Important notice

!!! danger
    A Danger notice

!!! info
    An Info notice

!!! hint
    A Hint

!!! seealso
    A See Also notice

!!! question
    A Question notice

!!! abstract
    An Abstract
