# Colorful Squares

This example demonstrates the creation of a colorful examples with four slots using a local template. It showcases how front matter can drive colours, slot routing, and final layout without touching TeX.

[![Colorful manifesto](../assets/examples/colorful.png)](../assets/examples/colorful.pdf)

=== "colorful.md"

    ```md
    --8<--- "examples/colorful/colorful.md"
    ```

=== "manifest.toml"

    ```toml
    --8<--- "examples/colorful/manifest.toml"
    ```

=== "template.tex"

    ```tex
    ---8<--- "examples/colorful/template.tex"
    ```

```md {.snippet data-caption="Demo" data-cwd="../../examples/colorful"}
--8<--- "examples/colorful/colorful.md"
```

To build this example, simply run:

```text
$ ls
colorful.md  manifest.toml  template.tex
$ texsmith colorful.md -t. --build
┌───────────────┬─────────────────────────────────────┐
│ Artifact      │ Location                            │
├───────────────┼─────────────────────────────────────┤
│ Main document │ /tmp/texsmith-x84gefq4/colorful.tex │
│ PDF           │ colorful.pdf                        │
└───────────────┴─────────────────────────────────────┘
```
