# Step 07 · Five analyses, and the direction they point to

Five agents were given step 07 independently: one to defend the batch
request/patch contract, one an inverted callback ABI, one to argue the mirror
is not the problem, one to move the traversals into Rust, and one to derive the
seam from first principles without seeing any proposal.

This is what they converged on, where they disagreed, and what to do.

## The convergence that decides it

**All five, by five different routes, found that ADR 0008 as drafted does not
drop `ir/` — which was its only stated justification.**

The reason is one sentence in the ADR: *"A replacement is IR, serialised as the
schema already defines it."* To answer a patch, TeXSmith must **construct** IR —
`Figure`, `Caption`, `Div`, `RawBlock`, `Str`, `Attrs`, `Image`, `SpanNode`,
`Para`, `Math`, `RawInline` — which needs the node types, the field names, the
id space and the span rules. The mirror does not disappear; it moves into the
patch serialiser.

Measured (defender of the batch contract, against his own brief): the classes
the passes construct or read are **218 of `model.py`'s 868 class lines** and
**157 of 442 `FIELDS` rows**. With the encode half of the codec, ~500–600
generated lines survive, still byte-compared in CI, still following every field
tmark adds to those twelve classes. *A node field added to `Image` or `Div` is
still a two-repository change.*

The first-principles analyst, who never saw the ADR until the end, named the
same thing as the single most likely mistake:

> Every pressure points that way — `snippet` "obviously" returns a `Figure`,
> `assets` "obviously" returns a `Caption` sibling. Each concession is locally
> cheap and each one keeps `ir/model.py` alive. **If the first `kind` shipped
> can return a subtree, the 2 195 lines never go.**

**So: a response must never carry IR.** That is the rule the ADR needed and did
not have. It is also a much harder constraint than the ADR imagined, because
three passes cannot obey it as shaped.

## What the contract cannot address, found independently

Blockers nobody had noticed before this analysis, each verified here:

- **`RefItem` has no `id`** (`src/texsmith/ir/model.py:537-542`: `key`,
  `key_span`, `prefix`, `suffix`, `suppress_author`). `doi` rewrites reference
  items, so `{node_id → patch}` cannot address them without a second address
  space or a whole-`Ref` round trip — and the round trip re-admits the decoder.
- **`assets` inserts a sibling.** `_caption_blocks` (`passes/assets.py:380-408`)
  reads the containing paragraph and the adjacent blocks and inserts a `Caption`
  next to them. "Insert a block after the block containing node N" is not
  expressible as a patch on N.
- **`scripts` needs a whole-document text query** after its own patches
  (`passes/scripts.py:191`), plus TeXSmith's private `script=`/`emoji=`
  attribute vocabulary to know what to skip. A request generator in the core
  would have to know TeXSmith's attribute names.
- **The default slot is non-contiguous** (`passes/slots.py:217`: the blocks not
  claimed by any slot), so the drafted `sections` row `[first_block, last_block]`
  cannot describe it. It needs a block-id list.
- **The MkDocs plugin builds a `Document` from nothing**
  (`packages/.../plugin.py:1661`) for a nav heading. There is no tree to patch.

Add the cost the defender measured: **20 conformance fixtures** across two
repositories, **11–15 boundary crossings per page** against ~4 today, four
address spaces, TeXSmith's `DEFAULT_PIPELINE` relocated into Rust, and an
all-or-nothing landing that contradicts this project's working rule — *one
step, one branch, one readable baseline diff*.

## The measurement that reframes the whole question

The sceptic was asked to argue the mirror is not the problem. His evidence:

- `src/texsmith/ir/model.py` was born **2026-09-11**. It is **three days old**.
- tmark's IR schema has changed **7 times ever**, 4 of them after the mirror
  existed.
- **Total hand-written cost over its entire life: ~37 lines in `walk.py`,
  once** (`9fbfe47`). Every other regeneration was running the generator.
- One schema change made TeXSmith *smaller*: typing `declare.glossary` deleted
  `passes/glossary.py`, 117 lines.
- The two defences the ADR does not credit are **already built**: the codec
  ignores unknown keys as serde does (`ir/codec.py:6`), and `SCHEMA_HASH` +
  `wheel_schema_mismatch()` turn a stale wheel into a named message.

The ADR priced a coupling that has cost 37 lines in three days, and proposed
nine request kinds, 20 fixtures and an all-or-nothing migration to remove it.

## The alternative two agents reached independently, from opposite briefs

**Ship the generated mirror from the tmark wheel.**

`crates/tmark-py/pyproject.toml:25` already sets `python-source = "python"`
with a real package (`python/tmark/__init__.py`, `_tmark.pyi`, `py.typed`), and
`crates/tmark-py/scripts/gen_stubs.py` already generates Python from Rust.
Moving `gen_ir_models.py` beside it and shipping `tmark.ir` means:

- TeXSmith's 2 195 lines go to **zero**, and `scripts/gen_ir_models.py` with them.
- One repository owns the schema; versioning is the wheel's.
- No new protocol, no new fixture, no ordering problem, no all-or-nothing.

It removes the ADR's *own stated cost* more completely than the ADR does, for
about a day. The defender of the batch contract wrote that it "strictly
dominates the ADR on the ADR's own stated cost" — in a report he was briefed to
write in the ADR's favour.

## The good idea inside ADR 0008, and my error in withdrawing step 06

Three of the five picked out `sections` as the part worth keeping, and the
first-principles analyst corrected the reasoning I used to withdraw step 06:

> What a `sections` query deletes is not `_section_end`'s ten lines; it is
> `ir/walk.py`, the `id()` reconciliation at `highlight.py:176`, and the
> per-body re-encode at `bodies.py:194`.

He is right and I measured the wrong quantity. `slots` reads the tree for five
scalars per top-level heading — `index, level, id, plain_text, span` — and
`passes/highlight.py:176-181` then reconciles `document.bodies` with
`document.ir` **by Python object identity** (`{id(old): new}`), because `slots`
partitioned *objects* instead of selecting indices. An outline query removes
the cause, not ten lines.

Step 06's withdrawal stands on its own grounds — the spec assigns heading
offsets and title promotion to TeXSmith by name — but the *outline primitive*
is worth more than I credited, and it now has three users (`slots`, `title`,
`headings`), which satisfies the rule that a generic mechanism needs two.

## What is already built and nobody used

`tmark.edit` and `tmark.edit_many` **exist in the shipped binding today**
(verified: `dir(tmark)`). That is the patch half of the contract, specified and
fixture-backed. A `tmark.select(doc, kinds)` would give the request half in one
function instead of nine kinds — and, crucially, it lands **pass by pass**,
because selecting over a tree TeXSmith still holds is a strict subset of
today's behaviour.

## The direction

**Reject ADR 0008 as drafted.** Its central claim is false, three of eleven
passes cannot fit its shape, and the coupling it prices has cost 37 lines.

Do these three instead, each small, each independently landable, each with its
own branch and baseline diff:

**1 · Ship `tmark.ir` from the wheel.** (~1 day, two repos.) Move
`gen_ir_models.py` next to `gen_stubs.py`; TeXSmith imports `tmark.ir` and
deletes 2 195 lines plus the generator plus the CI drift check. This is the
whole of the ADR's stated benefit, without the ADR.

**2 · `tmark.outline(doc)` as its own small ADR.** (~2 days, two repos.)
Returns `{index, level, id, text, span}` per top-level heading, plus the heading
levels inside containers that `headings` needs. Serves `slots`, `title` and
`headings`; removes the `id()` reconciliation and the per-body re-encode. Lands
alone, verifiable by the existing baseline.

**3 · Id and span custody.** (~1 day.) The one argument for 07 that survived
the sceptic, and it is a *correctness* argument: `IdAllocator.floor` and the
span rules (`highlight.py:15` "span rule 1", `emoji.py:25` "span rule 2") are
core invariants that TeXSmith re-derives with nothing enforcing them. A span
copied onto synthesised text is a location that exists and is wrong — the bug
class step 03 found twice. Let the core mint ids and spans for a synthesised
subtree.

**Then stop and measure.** If a tmark rename breaks the passes twice in a
quarter, reopen requests on evidence — with `select` + the existing
`edit_many`, pass by pass, and the rule this analysis produced written into it:

> **A response carries an answer, never a tree.** A path, a key, a font name, a
> token stream, or a typed failure. The shape of every rewrite lives in Rust.

## What was done, and what the doing changed

**Move 1 · `tmark.ir` ships from the wheel — done.** `src/texsmith/ir/`
(2 195 lines), `scripts/gen_ir_models.py` (822) and the CI drift check are
deleted; tmark generates and ships `tmark.ir.{model,codec,walk}`.
`src/texsmith` 35 141 → 33 061.

The move surfaced one thing the analyses had not: `model.py` imported `Span`
and `NO_SPAN` *from TeXSmith*, so the mirror could not simply move. `Span` is
`tmark_ir::span`, and the schema states its wire form — "Byte span as
[file, start, end]" — yet the Python restatement lived on the host side and the
generated models imported it back, kept in step by hand. It is generated from
the schema now, with `to_json`/`from_json`, because that form is the schema's;
`texsmith.diagnostics` imports it. One definition where there were two halves.

**Move 2 · the outline query — not needed, and the defect fixed without it.**
The analysis attributed two defects to a missing `outline`. Both were
TeXSmith's own:

- The `id()` reconciliation at `highlight.py:176` was caused by `slots`
  storing block *objects*. `SlotBody` now holds **indices** and `blocks_of(ir)`
  derives the view; `highlight` returns the rebuilt tree and nothing else. No
  binding, no ADR, no second repository. It also removed a silent failure:
  `mapping.get(block, block)` fell back to the stale block, so a body that lost
  identity rendered un-highlighted rather than raising.
- The per-body re-encode at `bodies.py:194` is **measured at 1.5 ms per slot**
  on the largest corpus document (`examples/book`, 206 top-level blocks, 81 KB)
  — about 11 ms for a seven-slot template against a ~1.2 s render. Under 1 %.
  Left alone: it is a design smell, not a cost.

So move 2 as scoped is closed, and `tmark.outline` is not proposed. The
remaining argument for it — that TeXSmith should not hold a tree at all — is
now weaker, because the tree it holds is the one tmark ships.

**Move 3 · id and span custody — done, and it did not need the core.** Three
passes cite a numbered rule in their docstrings — `highlight.py:15` "the
``Div`` keeps the block's id and span (span rule 1)", `emoji.py:25` and
`var.py:6` "the source span and a fresh id (span rule 2)". **Those rules were
written down nowhere**, in either repository: grep finds only the citations.

Measured before proposing anything: 73 documents through the full conversion
and 22 through the passes alone give **zero duplicate node ids and zero spans
naming an unregistered file**. The rules are obeyed. What was missing was the
statement and the check, not a mechanism — so the framework's docstring now
states all three, and 46 parametrised cases run every committed pass fixture
through its pass and assert the two that can be checked mechanically.

The synthesis had proposed a binding so the core would mint ids and spans for
synthesised subtrees, on the grounds that nothing enforced the rules. Nothing
did; something does now, for a docstring and 46 test cases.

## The shape of the result

All three moves are done and **none of them needed the contract, a new
binding, or a change to the frontier.**

| | proposed | what it actually took |
| - | -------- | --------------------- |
| 1 | ship the mirror from the wheel | that, plus generating `Span` where the schema defines it |
| 2 | a `tmark.outline` query | `SlotBody` holding indices; the re-encode measured negligible and left |
| 3 | a binding for id/span custody | a docstring and a test — the rules were already obeyed |

`src/texsmith` 35 141 → 33 061. 1 311 tests, parity 196/54/0.

The pattern is worth keeping: each move shrank on contact with a measurement.
ADR 0008 priced a coupling at nine request kinds and twenty fixtures; the
coupling had cost 37 lines in three days. The outline query was priced at a
cross-repository ADR; the defect under it was a local one about object
identity. The custody binding was priced at a fourth abstraction seam; the
invariant it would enforce already held. **Measure the pain before designing
the cure.**

## Status

ADR 0008 is marked rejected-as-drafted in tmark, with what survives it — the
rule that a response carries an answer and never a tree, for whoever revisits
requests on evidence. `tmark.edit`/`edit_many` already ship, so that day can
start from `select` and land pass by pass.

Moves 1, 2 and 3 are done.
