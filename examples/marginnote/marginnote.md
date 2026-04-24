---
press:
  title: Margin Notes
  subtitle: The `{margin}[…]` inline extension
  authors:
    - TeXSmith
---

# Margin Notes

TeXSmith's margin-note extension adds a single inline shorthand to the
unified `{keyword}[content]` family already used by `{index}[term]` and
`{latex}[payload]`. The syntax is:

```
{margin}[note text]{side?}
```

where `side` is an optional single-letter suffix — `l`, `r`, `o`, or `i` —
selecting a margin explicitly. It compiles down to `\marginnote{…}` from the
`marginnote` LaTeX package (auto-loaded on first use).

## Default placement

No suffix means the document's default side. In a `oneside` layout that's
the right margin; in a `twoside` layout, the outer margin (so the note
flips automatically between recto and verso pages).

Most readers appreciate a short quip{margin}[default note] that sits
beside the paragraph without interrupting the flow. When margin notes are
kept brief and self-contained, they feel like a friendly aside rather than
a distraction.

## Forced side

Force the left margin with `{l}` and the right margin with `{r}`. Because
the switch is scoped to a LaTeX group, subsequent unqualified notes still
follow the document's default placement.

Some diagrams read better when labelled on the left{margin}[left-hand
pointer]{l}, while running commentary fits the right-hand
margin{margin}[right-hand commentary]{r} more naturally. Mixing the two in
close succession is fine — each note is independent.

## Inline formatting

Margin notes pass through the full inline-Markdown parser, so they support
the usual **bold**, *italic*, `inline code`, and [links](https://example.org).

Viscoelastic materials can be approximated as linear{margin}[**Hooke's**
law applies at small strain where the stress is *proportional* to the
strain] under moderate stress, but non-linear effects dominate above the
yield point.

## Longer notes

The package handles multi-sentence notes gracefully. They line-wrap in the
margin and do not disturb the main text's baseline
grid.{margin}[Longer notes wrap over several lines and keep flowing down
the margin. Keep them concise so the reader can scan them without losing
the thread of the main text.]

Below, a denser example mixing sides and inline styles:

- Classical mechanics{margin}[see Newton, *Principia*, 1687]{l} predates
  the calculus of variations.
- Modern formulations rely on Lagrangians{margin}[or Hamiltonians for
  energy-based analyses] and variational principles.
- Quantum mechanics{margin}[introduces non-commuting
  observables]{r} follows in the 20th century.

## Inner / Outer

In a `twoside` layout — like this article — `{o}` (outer) and `{i}` (inner)
are MVP aliases of `{r}` and `{l}` respectively. On single-side documents
they behave identically to their counterparts.
