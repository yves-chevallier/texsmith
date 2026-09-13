# TeXSmith specifications

Design documents for the migration of TeXSmith onto the **TMark** core.

The TMark language specification itself is **not** kept here any more: it
lives in the `tmark` repository (`spec/tmark.md`, with its conformance
fixtures under `spec/conformance/`), which is the single source of truth for
the dialect, its IR and its tooling. `make spec` builds that copy
(`TMARK_SPEC=../tmark/spec/tmark.md` by default). The user guide in
[`docs/`](../docs) describes what ships today; the spec describes where the
dialect is headed.

## Documents

[`tmark-migration.md`](tmark-migration.md)
: The migration plan: current state, target architecture, decisions,
  phases, construct gap audit, difficulties and risks, sequencing.

[`migration/`](migration/)
: Design notes, one per difficulty of the plan: the web (MkDocs) profile,
  fragment contracts replacing the Jinja partials, the Rust writers and the
  Python passes, the migration of the examples, the Python-side IR models
  and pass framework.

## Process

The spec is the source of truth. A syntax change starts as a spec change
and a conformance fixture in the tmark repository, then reaches the parser,
the printer, the writers, the bindings and finally TeXSmith. The Python-
Markdown extensions of TeXSmith are frozen: no new syntax is added to them.

## After the migration

`refactoring/status.md` is the standing note of the SOLID / DRY / SSOT / KISS
pass that follows it: what it decided, what shipped, what is left, and the
traps it fell into. Read it before continuing that work.
