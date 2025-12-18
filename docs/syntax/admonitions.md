# Admonitions

Admonitions are little callout blocks for surfacing notes, warnings, tips, and whatever else you need to highlight. Python-Markdown’s `admonition` extension powers them.

You can render them in two flavors. The plain/static variant looks like this:

```markdown
!!! note "This is a Note"
    Any number of other indented markdown elements.

    This is the second paragraph.
```

!!! note "This is a Note"
    Any number of other indented markdown elements.

    This is the second paragraph.

Prefer collapsible callouts? Use the foldable form:

```markdown
??? note "This is a Note"
    Any number of other indented markdown elements.

    This is the second paragraph.
```

??? note "This is a Note"
    Any number of other indented markdown elements.

    This is the second paragraph.

## LaTeX Rendering

TeXSmith maps admonitions onto the `tcolorbox` package automatically, so they come through in LaTeX without extra work. Template authors can still restyle them via the preamble or dedicated slots.

Built-in templates like `article` and `book` ship with sensible defaults. Tweak the look by setting `callout_style` in front matter (or via `--attribute callout_style=<style>`):

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

    ```yaml {.snippet caption="Demo" width="70%"}
    cwd: ../../examples/admonition
    sources:
      - admonition.md
    press:
      callout_style: fancy
    ```

=== "Classic Admonitions"

    ```yaml {.snippet caption="Demo" width="70%"}
    cwd: ../../examples/admonition
    sources:
      - admonition.md
    press:
      callout_style: classic
    ```

=== "Minimal Admonitions"

    ```yaml {.snippet caption="Demo" width="70%"}
    cwd: ../../examples/admonition
    sources:
      - admonition.md
    press:
      callout_style: minimal
    ```

## Built-in Admonition Types

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
