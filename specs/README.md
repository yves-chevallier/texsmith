# TeXSmith specifications

Design documents for **TMark**, the Markdown dialect understood by TeXSmith.
This directory holds specification drafts — not user documentation. The user
guide lives in [`docs/`](../docs); when a spec and the docs disagree, the docs
describe what ships today and the spec describes where the dialect is headed.

## Documents

[`tmark.md`](tmark.md)
: **TMark — TeXSmith Markdown** (draft 3, working draft). A consolidated
  specification proposal for the dialect: philosophy, document model (four
  syntactic families, two sigils, registries), conformance classes and
  profiles, front matter layout, and a node catalogue that gives every IR
  node its canonical form, accepted sugar, degradation class and backend
  mapping. Constructs marked *(proposed)* are not implemented yet; everything
  else describes shipping behaviour. Draft 3 supersedes draft 2 — the review
  that motivated it and each decision are recorded in Appendix A, open
  questions in Appendix B, PyMdownX-only sugar in Appendix C, and every
  deprecated spelling with its horizon in Appendix D.

## Purpose

TMark exists to give scientific and technical writing a Markdown that is
*canonical* (one representation per feature in the document model, enabling
lint/format/round-trip tooling), *permissive* (the common MkDocs/PyMdownX and
Pandoc spellings keep working), and *honest about its deviations* (every
construct is classified by how it degrades in a plain CommonMark renderer).
The specification is the reference for future work on the parser, the
canonical printer, `tmark fmt`/`lint`, and editor support.

## Status and process

These documents are drafts under active discussion. Normative wording
("MUST", "SHOULD") is aspirational until a conformance suite exists. Changes
go through pull requests like any code change; substantial syntax decisions
should update Appendix A (divergences) or Appendix B (open questions) so the
history of choices stays traceable.
