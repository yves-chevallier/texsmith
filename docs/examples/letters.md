# Letters

TeXSmith include a built-in letter template based on the KOMA-Script `scrlttr2` class. Below are three examples of letters formatted according to different national standards: **DIN** (Germany), **SN** (Switzerland), and **NF** (France).

The letter template is builtin to TeXSmith; to use it, set `-tletter` on the command line or `template: letter` in your document frontmatter.

=== "DIN (Germany)"

    ```yaml {.snippet caption="Download PDF"}
    width: 70%
    cwd: ../../examples/letter
    sources:
      - letter.md
    press:
      format: din
    drop_title: true
    fragments:
        ts-frame
    press:
    frame: true
    ```

=== "SN (Switzerland)"

    ```yaml {.snippet caption="Download PDF"}
    width: 70%
    cwd: ../../examples/letter
    sources:
      - letter.md
    press:
      format: sn
    drop_title: true
    fragments:
        ts-frame
    press:
    frame: true
    ```

=== "NF (France)"

    ```yaml {.snippet caption="Download PDF"}
    width: 70%
    cwd: ../../examples/letter
    sources:
      - letter.md
    press:
      format: nf
    drop_title: true
    fragments:
        ts-frame
    press:
    frame: true
    ```

Here is the source code for the letter example used above:

=== "Letter"

    ```markdown
    --8<--- "examples/letter/letter.md"
    ```

=== "Template"

    ```latex
    --8<--- "src/texsmith/templates/letter/template/template.tex"
    ```

=== "Manifest"

    ```toml
    --8<--- "src/texsmith/templates/letter/manifest.toml"
    ```

To build the examples, use the following commands:

```bash
texsmith letter.md --build # for default format (DIN)
texsmith letter.md --build -aformat sn  # for SN format
texsmith letter.md --build -aformat nf  # for NF format
```

## Standards

### DIN 5008

Among all existing standards, **DIN 5008** is by far the most widely adopted reference for business correspondence in Germany. It prescribes layout rules, font sizes, margins, and a whole constellation of formatting details to guarantee consistency and professionalism in written communication. It is quite possibly the most detailed standard of its kind, specifying exact margin dimensions, the precise positioning of address blocks, the full structural blueprint of a professional letter, and fine-grained typographic conventions.

I haven’t personally dived into the full paid specification, but it’s safe to assume that KOMA-Script’s letter template draws heavily from it—and by extension, so does TeXSmith.

### NF Z 11-001

The former French AFNOR standard **NF Z 11-001**, replaced by ISO 269 back in 1998, defined the presentation rules for administrative letters in France. It described margins, address placement, letter structure, and typographic conventions intended to ensure clarity and uniformity in official documents. Although the standard is no longer active, it has left a lasting imprint on French administrative writing practices, and echoes of it can still be found in contemporary templates.

### ISO 214

**ISO 214** is an international standard specifying the layout conventions for commercial letters. It defines margins, address placement, structural order, and typographic rules to ensure a clear and professional presentation of business correspondence across borders. Its purpose is to harmonize commercial letter-writing practices between countries, smoothing out differences and making international communication a little more predictable.

## Why We Ultimately Chose scrlttr2

While our documentation already covers the underlying standards that govern letter layout, what actually matters in practice is finding a tool that can embody these rules with precision, consistency, and a healthy respect for typographic sanity. This is the point where LaTeX -- and specifically KOMA-Script’s `scrlttr2` -- quietly distinguishes itself from the rest. Designed in the German tradition of rigorous typesetting, `scrlttr2` follows the logic of formal letter standards with an almost pedantic accuracy, offering a layout engine that behaves predictably and stays faithful to the structural constraints imposed by modern correspondence norms. Yet it remains flexible enough to emulate the conventions of other national styles without falling apart or requiring awkward hacks.

In short, choosing `scrlttr2` was less about tradition and more about engineering. It gives us a letter typesetting engine that is standards-aware, robust enough for large-scale automation, and structured enough to keep our layouts consistent across contexts. It is not the easiest tool, nor the most forgiving, but for anyone who values correctness, longevity, and the quiet satisfaction of seeing a letter snap perfectly into place, it is simply the right one.
