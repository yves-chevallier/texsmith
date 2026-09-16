# TeXSmith specifications

Design documents of the migration of TeXSmith onto the **TMark** core. The
migration is done (September 2026); these notes are its record and the
reference the source code points at. `merge-tasklist.md` is the live list of
what remains before the merge and the release.

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
the printer, the writers, the bindings and finally TeXSmith.

## After the migration

`refactoring/status.md` is the standing note of the SOLID / DRY / SSOT / KISS
pass that follows it: what it decided, what shipped, what is left, and the
traps it fell into. Read it before continuing that work.

[`zensical.md`](zensical.md)
: What Zensical is, what it does not offer a plugin, and the strategy for
  keeping one source for the site and the PDF when MkDocs is no longer the
  generator. Recorded against Zensical 0.0.60 before the TMark migration, with
  a preamble on what the migration changed under it, and closing sections on
  what shipped, what migrating the HEIG-VD handbook taught, and how the
  versioned deploy replaced `mike` (2026-09-16).
