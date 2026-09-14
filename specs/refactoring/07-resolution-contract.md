# Step 07 · The resolution contract, assessed

> **Superseded on 2026-09-14 by `07-synthesis.md`.** Five independent analyses
> found that the contract proposed below does not drop `ir/` either: its
> patches are IR, so the host keeps the node types in order to construct them.
> This document's *measurements* stand; its conclusion does not. Read the
> synthesis for the direction.

What the request/patch contract would cost and buy, measured against the code
rather than estimated. Read `status.md` first; this is the detail behind its
step 07 entry, and it revises that entry's scope.

## The proposal, as the memo states it

    tmark    → typed requests   [{node_id, kind, payload}]   media · DOI · link · font
    texsmith → resolutions       {node_id → patch | literal}  I/O · network · cache · build
    tmark    → applies the patch and writes

> One contract serves four passes (`assets`, `emoji`, `doi`, `snippet`). It is
> typed, it is *finite* — TeXSmith never sees the whole tree — and it is the
> **only** route that drops `ir/` (2 195 lines, untouched).

## The finding: four passes is the wrong scope, and it would make things worse

`ir/` is 2 195 lines — `model.py` 1 496, `walk.py` 277, `codec.py` 402 — and it
exists because the passes walk a Python tree. Dropping it requires that **no**
pass need the tree.

The four passes the memo names are 990 lines. Seven passes remain, 1 083 lines,
and six of them construct or match `model.*` node classes:

| pass | lines | node types it touches |
| ---- | ----: | --------------------- |
| `include` | 283 | `Include`, `Block`, `Para`, `Str`, `Image`, `CodeBlock`, `Footnote`, `AbbrDef`, `Attrs`, `Span` |
| `slots` | 244 | `Document`, `Block`, `Header` |
| `scripts` | 211 | `Str`, `Span`, `Abbr`, `Code`, `Math`, … (11) |
| `highlight` | 182 | `CodeBlock`, `Div`, `RawBlock`, `Code`, `Attrs`, … (9) |
| `var` | 76 | `Var`, `Str`, `Node` |
| `title` | 38 | `Header` |
| `headings` | 49 | none — it works on `SlotBody` |

So **step 07 at the stated scope does not drop `ir/`**. Worse, it would leave
two ways to modify a document running in parallel — a request/patch contract
for four passes and a Python tree walk for seven — which is the shape step 08
has just spent three commits removing from the fragment activation. A second
mechanism is not a half-migration; it is a new defect with a migration
attached.

The memo half-says this itself: *"Migrating the pure passes alone leaves
`ir/model.py` and `codec.py` entirely in place."* It is true in both
directions. 06 without 07 does not drop `ir/`; 07 without 06 does not either.
And **06 is withdrawn** (`status.md`): the spec assigns `headings`, `title` and
the template half of `slots` to TeXSmith by name.

## The finding that rescues it: the contract is not limited to four passes

The memo scopes the contract to passes that need I/O per node. That is not the
constraint. The constraint is whether a pass is a **per-node replacement** or a
**restructuring**, and on inspection almost every pass is the former:

| pass | shape | fits `{node_id → patch}`? |
| ---- | ----- | ------------------------- |
| `assets`, `emoji`, `doi`, `snippet` | node → node, needs I/O | yes (the memo's four) |
| `highlight` | `CodeBlock` → `Div` + `RawBlock` child | yes — one node in, one subtree out |
| `scripts` | `Str` → sequence of `Str` / `Span{script}` | yes — one node in, a sequence out |
| `var` | `Var` → `Str` | yes |
| `title` | delete one top-level `Header` | yes, a patch that removes |
| `include` | one `Include` → N blocks | yes, and `Loader` already exists for it |
| `slots` | partition the top-level block list | **no** — a different shape |
| `headings` | touches no IR | n/a |

Ten of eleven fit. `slots` is the one that does not, and it does not need to:
it never needs the tree either. What it needs is an **index of the top-level
headers** — `{node_id, level, id, text, first_block, last_block}` — to match a
selector against, and then a write of a named block range. That is a query and
a ranged write, not a tree.

With `slots` served by a section index, no pass needs `model.*`, and the 2 195
lines go.

## What this means for the order

1. **06 stays withdrawn.** It moved passes; this moves a contract. The spec's
   frontier is untouched by 07 — TeXSmith still decides *what* a slot is, *which*
   template, *where* an include is looked up. It stops holding a Python mirror
   of the tree in order to act on those decisions.
2. **The contract must be designed for all eleven at once**, even if it is
   implemented in stages, or the staging itself creates the second mechanism.
   The order that avoids that: define the full request/patch/section-index
   contract, then migrate passes into it one at a time, and delete `ir/` when
   the last one lands — not before.
3. **`slots` decides the contract's shape.** It is the only pass the memo's
   three-line sketch cannot express, and it is the one to design first. A
   contract that serves `assets` and not `slots` is the four-pass version
   again.

## Cost

`ir/model.py` is generated from tmark's schema and compared byte for byte in
CI, so it is not maintenance TeXSmith carries. The 2 195 lines are a *coupling*
cost, not an upkeep cost: every IR change is a two-repository change today
because the Python mirror must follow. That is the real prize, and it is worth
stating as such rather than as a line count.

Against it: eleven passes rewritten, a new binding surface, and a contract that
must round-trip every construct the passes touch. This is the bet the memo
calls it. Nothing here makes it smaller — only better scoped.

## Status

**Proposed, not started.** The tmark counterpart is
`design/decisions/0008-resolution-requests.md`, also proposed. Neither should
be implemented before `tmark-migration` merges, per
`specs/migration/merge-readiness.md`.
