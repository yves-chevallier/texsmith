# Headings

Headings are your document's scaffold: Markdown `#` marks become LaTeX `\section`, `\subsection`, and friends. TeXSmith retunes them using template settings, document base levels, and promotion rules so the hierarchy stays sane even when the source is messy.

Markdown is loose: some files start at `##`, others at `###`, and multi-file builds mix it all. TeXSmith computes offsets per fragment to line things up: find the shallowest heading, derive an offset, then add the template base level. This page walks that math, how title promotion changes it, and how slots keep fragments independent.

## How offsets are computed

1. Drop any sections routed to slots (e.g. `abstract`) before aligning the remaining content for that slot.
2. If promotion is on and the first heading is uniquely the highest, it becomes metadata and is ignored for offsets.
3. Look at the shallowest heading that remains:
   - `<h1>` → offset `0`
   - `<h2>` → offset `-1`
   - `<h3>` → offset `-2`
   - No headings → offset `0`
4. The effective base level for a fragment is:

   ```text
   template slot base + document base_level + fragment offset
   ```

5. The rendered LaTeX level is `html_level + effective_base - 1`.

Offsets are per fragment: each slot fragment gets its own pass, so moving a heading into an abstract slot cannot force the main matter down a level.

## Template and document base levels

Classic LaTeX classes anchor headings differently: `article` tops out at `\section`, while `memoir` can start at `\chapter` or `\part`. Templates encode that base level per slot: abstract as a section, main matter as a chapter, etc. Adjust it per document via front matter or CLI; the template default is used if you set nothing.

=== "Front matter"

    ```yaml
    press:
      template: book
      base_level: chapter # To not use parts by default
    ```

=== "CLI"

    ```bash
    texsmith doc.md --template book --base-level chapter
    ```

## Promotion rules

Promotion lifts the first heading into the document title. Because that heading leaves the body, the next shallowest heading drives the offset. Promotion is on by default: if there is no metadata title and the first heading is uniquely the shallowest, it is promoted and skipped in the offset math.

A declared `title` in front matter disables promotion. So do `--no-promote-title` on the CLI and `TitleStrategy.NONE` in the Python API.

`--strip-heading` / `TitleStrategy.DROP` removes the first heading without promoting it.

Want an explicit title plus promotion? Declare `title`, keep promotion on, and the declared title wins while headings are still measured against the remaining body.

## Worked examples

All examples use the `article` template (`base_level=section`):

- Metadata title present; headings start at `##`: fragment offset `-1` + template base `1` → first heading renders as `\section`, nested `###` as `\subsection`.
- No metadata title; first heading is `# Title`: it is promoted and ignored for offsets, so the remaining `##` headings still become `\section`.
- Headings begin at `##` with no `#` anywhere: offset `-1` again, so the highest heading still aligns to `\section`.
- Slot extraction: if `# Abstract` is routed to the `abstract` slot and stripped there, the remaining main-matter fragment starts at `##` and is aligned to `\section` (the removed `#` does not push sections down to subsections).

## Multidocument behaviour

When rendering multiple documents, each document (and each of its slot fragments) computes its own offset independently. A root title in a multi-file build does not block promotion in subdocuments, and each slot still adds the template base level before applying the fragment offset.

## Quick reference

- Offsets are `1 - shallowest_heading_level` after promotion/slot stripping.
- Effective base = template slot base + document `base_level` + fragment offset.
- Promotion is default; disable with `--no-promote-title` or a declared title.
- Slots are aligned independently; moving a heading to a slot never changes the
  offset of the remaining content.
