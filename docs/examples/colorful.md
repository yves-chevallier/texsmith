# Colorful Squares

This example shows off a custom poster-ish template with four slots wired through a local template. Front matter steers colors, slot routing, and layout—no LaTeX tweaks needed.

```md {.snippet data-caption="Demo" data-width="60%" data-frame="false" data-cwd="../../examples/colorful"}
--8<--- "examples/colorful/colorful.md"
```

The YAML front matter picks the template (`.`), sets the palette, and feeds each slot. Colors live under `colors`, and slot content under `slots`.

The manifest defines defaults, available attributes, and where they get injected.

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

Build it with:

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
