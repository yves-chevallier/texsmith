# Cross-document references

A counter number only exists inside the conversion that allocated it. A second
document citing `FW-10` has no way to know what `FW-10` is, and — worse — no way
to notice when a renumbering turns it into `FW-12`. Hard-coded numbers in a
sister document break silently, which is exactly the maintenance
[custom counters](counters.md) remove *inside* a document.

TeXSmith closes the loop the way DocBook's *target database* and Sphinx's
`objects.inv` do: every conversion publishes a small JSON **inventory** next to
its output, and a citing document declares the inventories it depends on.

```yaml
# firmware-review.md — the document that publishes
---
title: Revue firmware
id: RHE-423
counters:
  fw:
    name: Constat
    format: "FW-{n:02d}"
---
```

```yaml
# hardware-review.md — the document that cites
---
title: Revue hardware
crossrefs:
  fwrev: build/firmware-review.refs.json
---
```

```markdown
L'écart est écrasé par l'étalement spectral (voir @fwrev:fw:pas-de-temps).
```

renders as

> L'écart est écrasé par l'étalement spectral (voir RHE-423-FW-10 p. 14).

## Identifying a document

`id` is a free label — a contract number, a report reference, whatever your
organisation numbers documents with (`document-id` is accepted as an alias). When the target document declares one,
a citation concatenates it with the item's label: `RHE-423` + `FW-10` →
**`RHE-423-FW-10`**. That is what makes the reference unambiguous outside the
document that defines it.

It is optional. Without it, a citation falls back to naming the document by its
title — `FW-10 (Revue firmware, p. 14)` — and without a title either, to the
bare label.

## The inventory

Each conversion writes `<document>.refs.json` beside its `.tex`:

```json
{
  "schema": 1,
  "document": {
    "id": "RHE-423",
    "title": "Revue firmware",
    "output": "firmware-review.pdf",
    "source": "../firmware-review.md",
    "source_sha256": "8b66c613…"
  },
  "anchors": {
    "fw:pas-de-temps": { "counter": "fw", "label": "FW-10", "page": 14 }
  }
}
```

It is delivered next to the artifact you asked for: in the directory for
`-o dir`, beside the PDF for `-o report.pdf`. Its `document.source` is stored
relative to its own location and is rewritten when it moves, so the staleness
check keeps working.

It is written in two passes, because the two halves of a reference become known
at different times. The keys and their labels are known while converting; the
**page numbers only exist once LaTeX has run**, and are harvested from the
`.aux` afterwards — the same source the `xr` package reads. A conversion without
`--build` therefore publishes an inventory without pages, and citations simply
omit the page.

!!! tip "Commit the inventory"
    It is a build artifact, but committing it makes renumbering *diffable*:
    `git diff` shows `FW-04 → FW-10` before you publish. For a contractual
    document, that diff is the review gate that catches a renumbering before it
    reaches a reader.

## Declaring and citing

```yaml
crossrefs:
  fwrev: build/firmware-review.refs.json # shorthand
  hwrev:
    inventory: ../hardware/build/hardware-review.refs.json
```

Paths are relative to the citing document. The alias is then the first segment
of the reference: `@fwrev:fw:pas-de-temps`.

Resolution is **explicit**: an alias never falls back to a local counter, and a
local counter can never be shadowed by an external one. `@fw:x` is always this
document's item, `@fwrev:fw:x` is always the other document's.

## An external citation is text, not a link

The target lives in a different PDF, so TeXSmith emits the formatted reference
as plain text rather than a `\hyperref` that would resolve to nothing. Local
references keep their live link.

## Diagnostics

This is the part that earns the feature. All of these are Python warnings, shown
by default and promotable to hard failures with `PYTHONWARNINGS=error`:

| Situation | Behaviour |
| --- | --- |
| the key is not published by the declared inventory | warning, and the citation renders as `[?fwrev:fw:disparu]` |
| the inventory file does not exist yet | warning, citations render as `[?…]` |
| the inventory's source changed since it was written | warning: the numbers you are citing may already be wrong |
| the inventory's source no longer resolves at all | warning: staleness can no longer be checked |
| the inventory uses a newer schema | warning, inventory ignored |

Warnings are attributed to the **citing document**, not to a TeXSmith source
line:

```
review/hardware-review.md:0: UserWarning: Cross-reference '@fwrev:fw:disparu' is not published by …
```

An unresolved citation is deliberately **visible in the output**. A silently
dropped reference is how a contractual document ships a hole.

## Build order

`hardware-review.pdf` now depends on `firmware-review.refs.json`, which is a
Makefile edge:

```makefile
build/hardware-review.pdf: hardware-review.md build/firmware-review.refs.json
```

Two documents citing each other need two passes, exactly like LaTeX's own
`.aux`: a missing inventory is a warning and not a failure, so the first build
produces the inventories and the second resolves the citations.

## Not implemented yet

Links from one PDF into another (`xr-hyper` does this with a PDF-viewer `GoToR`
action), sections, figures and tables in the inventory (only counters are
published yet), custom citation formats, and any form of automatic build
ordering.
