# Letters

TeXSmith include a built-in letter template based on the KOMA-Script `scrlttr2` class. Below are
three examples of letters formatted according to different national standards: DIN (Germany),
SN (Switzerland), and NF (France).

=== "DIN (Germany)"

    ````md {.snippet data-caption="Download PDF" data-attr-format="din" data-layout="2x1" data-frame="true" data-width="80%"}
    ---8<--- "examples/letter/letter.md"
    ````

=== "SN (Switzerland)"

    ````md {.snippet data-caption="Download PDF" data-attr-format="sn" data-layout="2x1" data-frame="true" data-width="80%"}
    ---8<--- "examples/letter/letter.md"
    ````

=== "NF (France)"

    ````md {.snippet data-caption="Download PDF" data-attr-format="nf" data-layout="2x1" data-frame="true" data-width="80%"}
    ---8<--- "examples/letter/letter.md"
    ````

```markdown
--8<--- "examples/letter/letter.md"
```

To build the examples, use the following commands:

```bash
texsmith letter.md --build # for default format (DIN)
texsmith letter.md --build -aformat sn  # for SN format
texsmith letter.md --build -aformat nf  # for NF format
```
