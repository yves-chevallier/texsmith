// texsmith.typ — the Typst contract functions the tmark writer calls
// (specs/migration/fragment-contracts.md §1, §3 rule 7). A minimal, template-
// independent definition of every `#ts-*` name so a body compiles on its own;
// a template restyles any of them by redefining the name after this prelude.
// TODO(migration 3.6/3.7): move these into the Typst side of the ts-* fragments.

#let ts-divider() = pagebreak(weak: true)

#let ts-lead(body) = strong(body)

#let ts-page(target) = context {
  let matches = query(target)
  if matches.len() > 0 { counter(page).at(matches.first().location()).first() } else { [?] }
}

#let ts-acr(key) = key

#let ts-gls(term) = emph(term)

#let ts-keys(..keys) = keys.pos().map(k => box(
  inset: (x: 3pt, y: 1.5pt), stroke: 0.5pt, radius: 2pt, baseline: 20%, text(size: 0.85em, k),
)).join([ #sym.plus ])

#let ts-index(..terms, registry: "", main: false) = none

#let ts-task(state, body) = {
  let mark = if state == "done" { sym.ballot.x } else if state == "partial" { sym.ballot } else { sym.ballot }
  [#mark #body]
}

#let ts-epigraph(body, source: none) = block(width: 100%, inset: (left: 40%))[
  #emph(body)
  #if source != none [#linebreak() #h(1fr) — #source]
]

#let ts-aside(body, side: "right") = place(
  if side == "left" { left } else { right },
  dx: if side == "left" { -12% } else { 12% },
  box(width: 10%, text(size: 0.8em, body)),
)

#let ts-script(slug, body) = body

#let ts-emoji(body) = body

#let ts-callout(body, kind: "note", title: none, id: none, collapsed: false) = block(
  width: 100%, inset: 8pt, radius: 3pt, stroke: 0.5pt + luma(160), fill: luma(245),
)[
  #if title != none [#strong(title)] else [#strong(upper(kind.first()) + kind.slice(1))]
  #v(0.3em)
  #body
]

#let ts-code(body, ..options) = block(width: 100%, body)

#let ts-div(name, body, ..attrs) = body
