# Headings

Heading alignment in TeXSmith follows a consistent set of rules: find the
shallowest heading in each fragment, compute an offset, then add the template
base level. This page explains that calculation, how promotion interacts with
it, and how slots influence the result.

## How offsets are computed

1. Remove any sections routed to slots (e.g. `abstract`) before aligning the
   remaining content for that slot.
2. If title promotion is enabled and the first heading is uniquely the highest,
   it becomes metadata and is ignored for offset calculation.
3. Look at the shallowest heading that remains:
   - `<h1>` → offset `0`
   - `<h2>` → offset `-1`
   - `<h3>` → offset `-2`
   - No headings → offset `0`
4. The effective base level for a fragment is:

   ```
   template slot base + document base_level + fragment offset
   ```

5. The rendered LaTeX level is `html_level + effective_base - 1`.

Offsets are per fragment: each slot fragment gets its own pass, so moving a
heading into an abstract slot cannot force the main matter down a level.

## Template and document base levels

- Templates set a default base level and per-slot overrides using `base_level`,
  `depth`, and `offset` in the manifest. For example, the built-in `article`
  template maps its main slot to `\section` (base level `1`), while the `book`
  template maps to `\chapter` (base level `0`).
- A document can add its own shift via `press.base_level` in front matter, the
  CLI `--base-level` flag, or `Document(base_level=…)`. Accepted values are the
  aliases `part`, `chapter`, `section`, `subsection`, or an integer.
- The document shift is added after the template slot base; then the fragment
  offset is applied.

## Promotion rules

- Promotion is on by default. If no metadata title exists and the first heading
  is uniquely the shallowest, it is promoted to metadata and dropped from the
  body. The offset then uses the next heading.
- A declared `title` in front matter disables promotion. So does `--no-promote-title`
  or `TitleStrategy.KEEP`.
- `--strip-heading` / `TitleStrategy.DROP` removes the first heading without
  promoting it.

## Worked examples

All examples use the `article` template (`base_level=section`):

- Metadata title present; headings start at `##`: fragment offset `-1` +
  template base `1` → first heading renders as `\section`, nested `###` as
  `\subsection`.
- No metadata title; first heading is `# Title`: the title is promoted and
  ignored for offsets, so the remaining `##` headings still become `\section`.
- Headings begin at `##` with no `#` anywhere: offset `-1` again, so the highest
  heading is still aligned to `\section`.
- Slot extraction: if `# Abstract` is routed to the `abstract` slot and stripped
  there, the remaining main-matter fragment starts at `##` and is aligned to
  `\section` (the removed `#` does not push sections down to subsections).

## Multidocument behaviour

When rendering multiple documents, each document (and each of its slot
fragments) computes its own offset independently. A root title in a multi-file
build does not block promotion in subdocuments, and each slot still adds the
template base level before applying the fragment offset.

## Quick reference

- Offsets are `1 - shallowest_heading_level` after promotion/slot stripping.
- Effective base = template slot base + document `base_level` + fragment offset.
- Promotion is default; disable with `--no-promote-title` or a declared title.
- Slots are aligned independently; moving a heading to a slot never changes the
  offset of the remaining content.
