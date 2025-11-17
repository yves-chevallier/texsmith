# Letters

TeXSmith include a built-in letter template based on the KOMA-Script `scrlttr2` class. Below are
three examples of letters formatted according to different national standards: DIN (Germany),
SN (Switzerland), and NF (France).

```markdown
--8<--- "examples/letter/letter.md"
```

To build the examples, use the following commands:

```bash
texsmith render letter.md --build # for default format (DIN)
texsmith render letter.md --build -aformat sn  # for SN format
texsmith render letter.md --build -aformat nf  # for NF format
```

=== "DIN (Germany)"

    [![DIN](../assets/examples/letter-din.png){width=60%}](../assets/examples/letter-din.pdf)

=== "SN (Switzerland)"

    [![SN](../assets/examples/letter-sn.png){width=60%}](../assets/examples/letter-sn.pdf)

=== "NF (France)"

    [![NF](../assets/examples/letter-nf.png){width=60%}](../assets/examples/letter-nf.pdf)
