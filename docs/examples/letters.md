# Letters

TeXSmith include a built-in letter template based on the KOMA-Script `scrlttr2` class. Below are
three examples of letters formatted according to different national standards: DIN (Germany),
SN (Switzerland), and NF (France).

The letter template is builtin to TeXSmith; to use it, set `-tletter` on the command line or
`template: letter` in your document frontmatter.

=== "DIN (Germany)"

    ````md {.snippet data-caption="Download PDF" data-attr-format="din" data-drop-title="true" data-frame="true" data-width="80%" data-cwd="../../examples/letter/"}
    ---8<--- "examples/letter/letter.md"
    ````

=== "SN (Switzerland)"

    ````md {.snippet data-caption="Download PDF" data-attr-format="sn" data-drop-title="true" data-frame="true" data-width="80%" data-cwd="../../examples/letter/"}
    ---8<--- "examples/letter/letter.md"
    ````

=== "NF (France)"

    ````md {.snippet data-caption="Download PDF" data-attr-format="nf" data-drop-title="true" data-frame="true" data-width="80%" data-cwd="../../examples/letter/"}
    ---8<--- "examples/letter/letter.md"
    ````

Here is the source code for the letter example used above:

=== "Letter"

    ```markdown
    --8<--- "examples/letter/letter.md"
    ```

=== "Template"

    ```latex
    --8<--- "src/texsmith/builtin_templates/letter/template/template.tex"
    ```

=== "Manifest"

    ```toml
    --8<--- "src/texsmith/builtin_templates/letter/manifest.toml"
    ```

To build the examples, use the following commands:

```bash
texsmith letter.md --build # for default format (DIN)
texsmith letter.md --build -aformat sn  # for SN format
texsmith letter.md --build -aformat nf  # for NF format
```
