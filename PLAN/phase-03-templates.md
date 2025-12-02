# Phase 03 — Template Cleanup (Article/Book/Letter)

## Goals
- Align built-in templates with clarified attribute rules and slot structure.
- Remove misplaced attributes/assets and add needed appendix support.

## Tasks
- Add `appendix` slot; insert appendix before backmatter when present.
- Remove template-shipped `.latexmkrc` assets; rely on core injector.
- Move `mermaid-config.json` to template root (next to manifest), adjust asset lookup.
- Remove/relocate attributes:
  - Drop `article: emoji` (handled by ts-fonts); use emitter if template must force a value.
  - Drop `article/book: preamble` if unused.
  - Drop `article: backmatter`.
  - Drop `book: columns` (memoir lacks twocolumn support).
  - Remove cover assets and attrs (`logo`, `cover`, `covercolor`) from book.
- Add manifest descriptions for book and letter similar to article.

## Tests / Acceptance
- Rendering article/book with/without appendix places content correctly.
- Assets copied without latexmkrc; mermaid config discovered from root.
- Book ignores twocolumn attribute and cover files removed.
- Template info output reflects new descriptions and removed attributes.
