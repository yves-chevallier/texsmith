# Headings

Headings are where TeXSmith does the most heavy lifting: it analyses every
document, figures out the shallowest heading, then lines up the entire hierarchy
with the target template. This section explains how that auto-alignment works,
how to tweak it, and how CLI flags map onto the Python API.

## Automatic alignment

TeXSmith always maps the highest heading it finds to the base level requested by
the runtime:

- Fragment mode (no template) defaults to `\chapter`.
- The built-in `article` template declares `base_level = 1`, so the highest
  heading becomes `\section`.
- Other templates can override this per slot; slot `offset` values stack on top.

If the first heading in your source is `## Overview`, TeXSmith notices that `##`
maps to level 2, subtracts one, and shifts every heading so the new top sits at
level 1.

=== "CLI"

    ```bash
    cat <<'EOF' > headings.md
    ## Overview

    Deep dive incoming.

    ### Details

    Paragraph text.
    EOF

    # Plain fragment output → \chapter, \section …
    texsmith render headings.md

    # Template output → \section, \subsection …
    texsmith render headings.md --template article --title-from-frontmatter \
      --output-dir build/headings
    ```

=== "Python API"

    ```python
    from pathlib import Path
    from texsmith.api.document import Document
    from texsmith.api.pipeline import convert_documents

    source = Path("headings.md")
    doc = Document.from_markdown(source)  # auto alignment enabled
    bundle = convert_documents([doc])
    print(bundle.combined_output())
    ```

## Base level offsets

Need to nudge the entire hierarchy up or down? Use the base level knobs:

- CLI: `--base-level <int>` shifts the detected heading upward
  (negative pulls toward chapters, positive pushes toward sublevels).
- Front matter: set `press.base_level` to bake the offset into the document.
- API: pass `base_level=` to `Document.from_markdown` or tweak
  `document.options.base_level`.

=== "CLI"

    ```bash
    # Turn the same ## heading into a subsection
    texsmith render headings.md --base-level 2

    # Or force it back to a chapter, even inside a template
    texsmith render headings.md -tarticle --base-level -1 \
      --title-from-frontmatter
    ```

=== "Python API"

    ```python
    doc = Document.from_markdown(Path("headings.md"), base_level=2)
    bundle = convert_documents([doc])
    # bundle now renders Overview as \subsection
    ```

Remember that base levels stack with template slot metadata. If a template slot
sets `depth = "subsection"` and you provide `base_level=1`, the resulting
headings start at `\subsubsection`.

## Heading indentation (`--heading-level`)

Base level changes where the first heading lands. The `--heading-level`
(`-h`) flag indents *every* heading by a constant amount after alignment. This is
handy when you embed documents into a larger structure and need an extra offset.

- CLI: `texsmith render intro.md -h 1` turns `#` into `\subsection`.
- API: pass `heading=` to `Document.from_markdown` or call
  `document.set_heading("subsection")`.

You can mix both knobs. For example, `--base-level 1 -h 2` shifts the document’s
top heading down to `\subsection` and then indents twice more, ending up at
`\subsubsection`.

## Managing titles

TeXSmith exposes three title strategies:

| Strategy                  | Trigger                                | Effect                                   |
| ------------------------- | -------------------------------------- | ---------------------------------------- |
| `KEEP`                    | default                                | Headings stay intact                     |
| `DROP` / `--drop-title`   | CLI flag / `TitleStrategy.DROP`        | Removes the first heading after alignment |
| `PROMOTE_METADATA`        | `--title-from-heading` / API property | Moves the first heading into metadata (title) |

When you promote a heading to metadata, the next heading inherits the top slot.
That’s why CLI template builds often add `--title-from-frontmatter`: it keeps
the leading `#` inside the body rather than absorbing it into the title page.

=== "CLI"

    ```bash
    # Promote the first heading to \title{} and re-align the rest
    texsmith render paper.md --title-from-heading --template article

    # Keep headings but drop the duplicate title in the body
    texsmith render paper.md --drop-title -tarticle
    ```

=== "Python API"

    ```python
    doc = Document.from_markdown(Path("paper.md"))
    doc.title_from_heading = True  # same effect as --title-from-heading
    ```

Behind the scenes, TeXSmith recalculates base levels after the title move so
your new top heading still matches the template.

## Templates, slots, and mixed documents

Templates can set a global base level (see `latex.template.attributes.base_level`
in the manifest) and per-slot overrides:

```toml
[latex.template.slots.mainmatter]
default = true
depth = "section"

[latex.template.slots.appendix]
base_level = 2  # start at \subsection regardless of inputs
strip_heading = true
```

Key takeaways:

- Slot `depth` and `base_level` values override the template default.
- Slot `offset` adds relative shifts (useful when crafting appendix ladders).
- Front matter entries under `press.slots.*` or CLI `--slot` flags can target
  different headings in the same document; each gets its own alignment pass.
- Titles promoted from headings are scoped per document, even when you feed the
  same source into multiple slots.

When combining multiple documents in a template session, TeXSmith aligns each
document individually before applying the slot base level. That means you can
mix files that start at `#` and `##` without worrying about mismatched
hierarchies—everything snaps to whatever the slot demands.

## Cheat sheet

- Use `--base-level` (CLI) or `base_level=` (API/front matter) to change where
  the first heading lands.
- Use `-h/--heading-level` or `heading=` to indent everything after alignment.
- `--drop-title` removes the first heading; `--title-from-heading` converts it
  into metadata.
- Templates can set their own defaults; slots can override them again.
- Alignment is automatic, so you can mix Markdown sources with different top
  headings without manual clean-up.
