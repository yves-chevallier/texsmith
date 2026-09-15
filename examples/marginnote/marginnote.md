---
press:
  title: Margin Notes
  subtitle: The `{aside}[…]` inline extension
  authors:
    - TeXSmith
---

# Margin Notes

TeXSmith's margin-note extension adds a single inline shorthand to the
unified `{keyword}[content]` family already used by `{index}[term]` and
`{raw latex}(payload)`. The syntax is:

```
{aside side=…}[note text]
```

where `side` is an optional placement — `left`, `right`, `outer` or `inner` —
selecting a margin explicitly. It compiles down to `\tsaside`: a `\marginpar`
that `marginfix` moves past the previous note on the document's own side, a
`\marginnote` fixed at its line on the other side or inside a box.

## Default placement

No suffix means the document's default side. In a `oneside` layout that's
the right margin; in a `twoside` layout, the outer margin (so the note
flips automatically between recto and verso pages).

Most readers appreciate a short quip{aside}[default note] that sits
beside the paragraph without interrupting the flow. When margin notes are
kept brief and self-contained, they feel like a friendly aside rather than
a distraction.

## Forced side

Force the left margin with `side=left` and the right margin with
`side=right`. Because
the switch is scoped to a LaTeX group, subsequent unqualified notes still
follow the document's default placement.

Some diagrams read better when labelled on the left{aside side=left}[left-hand
pointer], while running commentary fits the right-hand
margin{aside side=right}[right-hand commentary] more naturally. Mixing the two in
close succession is fine — each note is independent.

## Inline formatting

Margin notes pass through the full inline-Markdown parser, so they support
the usual **bold**, *italic*, `inline code`, and [links](https://example.org).

Viscoelastic materials can be approximated as linear{aside}[**Hooke's**
law applies at small strain where the stress is *proportional* to the
strain] under moderate stress, but non-linear effects dominate above the
yield point.

## Longer notes

The package handles multi-sentence notes gracefully. They line-wrap in the
margin and do not disturb the main text's baseline
grid.{aside}[Longer notes wrap over several lines and keep flowing down
the margin. Keep them concise so the reader can scan them without losing
the thread of the main text.]

Below, a denser example mixing sides and inline styles:

- Classical mechanics{aside side=left}[see Newton, *Principia*, 1687] predates
  the calculus of variations.
- Modern formulations rely on Lagrangians{aside}[or Hamiltonians for
  energy-based analyses] and variational principles.
- Quantum mechanics{aside side=right}[introduces non-commuting
  observables] follows in the 20th century.

## Inner / Outer

In a `twoside` layout — like this article — `{o}` (outer) and `{i}` (inner)
are MVP aliases of `{r}` and `{l}` respectively. On single-side documents
they behave identically to their counterparts.
