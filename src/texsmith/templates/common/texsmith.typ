// texsmith.typ — the Typst mirror of the LaTeX fragment contracts
// (specs/migration/fragment-contracts.md §1, §3 rule 7). One hyphenated
// function per contract; named arguments mirror the LaTeX keys, the content
// comes last. The tmark Typst writer emits these calls; this file is copied
// next to the .typ and a template overrides a function after importing it:
//
//   #import "texsmith.typ": *
//   #let ts-divider() = v(1em)

// ---------------------------------------------------------------- palette

#let ts-callout-colors = (
  note: (bg: rgb("ecf3ff"), frame: rgb("448aff")),
  abstract: (bg: rgb("e5f7ff"), frame: rgb("00b0ff")),
  summary: (bg: rgb("e5f8fb"), frame: rgb("00b8d4")),
  info: (bg: rgb("e5f8fb"), frame: rgb("00b8d4")),
  seealso: (bg: rgb("e5f8fb"), frame: rgb("00b8d4")),
  tip: (bg: rgb("e5f8f6"), frame: rgb("00bfa5")),
  hint: (bg: rgb("e5f8f6"), frame: rgb("00bfa5")),
  success: (bg: rgb("e5f9ed"), frame: rgb("00c853")),
  question: (bg: rgb("effce7"), frame: rgb("64dd17")),
  warning: (bg: rgb("fff1d6"), frame: rgb("ffb200")),
  caution: (bg: rgb("fff8e1"), frame: rgb("ff9100")),
  failure: (bg: rgb("ffeded"), frame: rgb("ff5252")),
  danger: (bg: rgb("ffe2e7"), frame: rgb("c62828")),
  important: (bg: rgb("ffe0f0"), frame: rgb("d81b60")),
  bug: (bg: rgb("fee5ee"), frame: rgb("f50057")),
  example: (bg: rgb("f2edff"), frame: rgb("7c4dff")),
  quote: (bg: rgb("f5f5f5"), frame: rgb("9e9e9e")),
  default: (bg: rgb("f0f0f0"), frame: rgb("808080")),
)

#let ts-callout-words = (
  note: "Note", tip: "Tip", warning: "Warning", important: "Important",
  danger: "Danger", info: "Info", hint: "Hint", seealso: "See also",
  question: "Question", abstract: "Abstract", summary: "Summary",
  success: "Success", caution: "Caution", failure: "Failure", bug: "Bug",
  example: "Example", quote: "Quote", theorem: "Theorem", lemma: "Lemma",
  corollary: "Corollary", proposition: "Proposition",
  definition: "Definition", proof: "Proof", default: "Note",
)

#let ts-capitalize(s) = {
  if s.len() == 0 { s } else { upper(s.slice(0, 1)) + s.slice(1) }
}

// ---------------------------------------------------------- ts-typesetting

// Lead-in of a paragraph (Para.lead): a run-in bold line.
#let ts-lead(body) = block(above: 0.6em, below: 0.3em, strong(body))

// Highlight is native (#highlight); kept for symmetry with \tsmark.
#let ts-mark(body) = highlight(body)

// A thematic break: paged output turns the page (decisions X2).
#let ts-divider() = pagebreak(weak: true)

// #ts-epigraph(source: [..])[body]
#let ts-epigraph(source: none, body) = {
  block(width: 100%, inset: (left: 40%), below: 1.5em)[
    #emph[“#body”]
    #if source != none [
      #v(0.2em)
      #align(right)[— #emph(source)]
    ]
  ]
}

// #ts-aside(side: "left")[body]: a margin note.
#let ts-aside(side: "right", body) = {
  let note = block(width: 2.4cm, text(size: 0.8em, body))
  if side == "left" or side == "inner" {
    place(left, dx: -2.8cm, note)
  } else {
    place(right, dx: 2.8cm, note)
  }
}

// #ts-progress(0.45, label: "label", thin: false)
#let ts-progress(value, label: none, thin: false, class: (), ..rest) = {
  // `class` carries the attribute classes of the bar (`{.thin .candystripe}`).
  let thin = thin or ("thin" in class)
  let bar-height = if thin { 6pt } else { 12pt }
  let v = calc.max(0.0, calc.min(1.0, float(value)))
  block(below: 0.6em)[
    #box(
      width: 9cm, height: bar-height, stroke: 1pt + black, fill: luma(235),
      radius: 1pt, clip: true,
      align(left, box(width: v * 100%, height: bar-height, fill: luma(100))),
    )
    #h(0.5em) #label
  ]
}

// #ts-icon("path"): an inline icon (emoji artifact mode).
#let ts-icon(path) = box(image(path), height: 1em)

// #ts-div("name", key: value)[body]: the generic container. Known names:
// multicolumn (cols:), tab (title:); anything else is transparent.
#let ts-div(name, ..args) = {
  let body = args.pos().at(0, default: [])
  let named = args.named()
  if name == "multicolumn" {
    columns(int(named.at("cols", default: 2)), body)
  } else if name == "tab" {
    if "title" in named { block(above: 0.8em, below: 0.4em, strong(named.title)) }
    body
  } else {
    body
  }
}

// ------------------------------------------------------------- ts-callouts

// #ts-callout(kind: "note", title: [..], id: "x", class: (..), collapsed: true)[body]
#let ts-callout(
  kind: "note", title: none, id: none, class: (), collapsed: false, ..attrs
) = {
  let body = attrs.pos().at(0, default: [])
  let key = if kind in ts-callout-colors { kind } else { "default" }
  let colors = ts-callout-colors.at(key)
  let heading = if title != none { title } else {
    ts-callout-words.at(kind, default: ts-capitalize(kind))
  }
  let content = block(
    width: 100%,
    stroke: (left: 3pt + colors.frame, rest: 0.4pt + colors.frame),
    radius: (right: 2pt),
    inset: 0pt,
    breakable: true,
    below: 1em,
  )[
    #block(width: 100%, fill: colors.bg, inset: (x: 0.8em, y: 0.5em),
      text(weight: "bold", heading))
    #block(width: 100%, inset: (x: 0.8em, y: 0.6em), body)
  ]
  if id != none [#content #label(id)] else { content }
}

// ----------------------------------------------------------------- ts-code

// #ts-code(title: [..], linenums: 1, hl-lines: ("2-3",), id: "x", caption: [..])[```lang … ```]
#let ts-code(
  title: none, linenums: none, hl-lines: (), id: none, caption: none, class: (), ..attrs
) = {
  let body = attrs.pos().at(0, default: [])
  let head = if title != none { title } else { caption }
  let listing = block(
    width: 100%,
    stroke: 0.4pt + luma(40),
    radius: 1pt,
    inset: 0pt,
    breakable: true,
    below: 1em,
  )[
    #if head != none [
      #block(width: 100%, inset: (x: 0.8em, y: 0.4em), stroke: (bottom: 0.4pt + luma(40)),
        text(weight: "bold", head))
    ]
    #block(width: 100%, inset: (x: 0.8em, y: 0.5em), body)
  ]
  if id != none {
    [#figure(listing, kind: raw, supplement: "Listing", caption: caption) #label(id)]
  } else {
    listing
  }
}

#let ts-codeinline(lang: none, body) = raw(body, lang: lang)

// ------------------------------------------------------------ ts-keystrokes

// #ts-keys("Ctrl", "Alt", "Del")
#let ts-keys(..keys) = {
  let boxes = keys.pos().map(k => box(
    stroke: 0.5pt + luma(60), fill: luma(240), radius: 1.5pt,
    inset: (x: 0.4em, y: 0.15em), baseline: 0.15em,
    text(size: 0.8em, font: "DejaVu Sans", k),
  ))
  boxes.join([ + ])
}

// -------------------------------------------------------------- ts-todolist

// #ts-task("done")[body]
#let ts-task(state, body) = {
  let mark = if state == "done" { "☑" } else if state == "partial" { "◪" } else { "☐" }
  [#mark #body]
}

// -------------------------------------------------------------- ts-glossary

#let ts-gls(key) = key
#let ts-acr(key) = key

// ----------------------------------------------------------------- ts-index

// #ts-index([a], [b], registry: "r", main: true): no-op (open question 6).
#let ts-index(..path, registry: none, main: false) = none

// ---------------------------------------------------------- ts-bibliography

// #ts-page(<label>): the page number of a label (textual references).
#let ts-page(target) = context { counter(page).at(target).first() }

// ----------------------------------------------------------------- ts-fonts

#let ts-script(slug, body) = body
#let ts-emoji(body) = text(
  font: ("Noto Color Emoji", "Noto Emoji", "Apple Color Emoji", "Segoe UI Emoji"),
  body,
)

// ---------------------------------------------------------------- ts-critic

#let ts-ins(body) = text(fill: rgb("1b7f3b"), underline(body))
#let ts-del(body) = text(fill: rgb("b3261e"), strike(body))
#let ts-subst(old, new) = [#ts-del(old) #ts-ins(new)]
#let ts-comment(body) = text(fill: luma(110), emph[/\* #body \*/])

// TeX logos (spec C33, feature `typography.tex-logos`): the writer emits
// `#ts-logo("XeLaTeX")` for the words of the closed list; `TeX`, `LaTeX`
// and `LaTeX2e` are typeset from their parts, any other word as prefix + logo.
#let ts-tex = [T#h(-0.1667em)#box(move(dy: 0.22em)[E])#h(-0.125em)X]
#let ts-latex = [L#h(-0.36em)#box(move(dy: -0.22em, text(size: 0.7em)[A]))#h(-0.15em)#ts-tex]
#let ts-logo(name) = {
  if name == "TeX" { ts-tex }
  else if name == "LaTeX" { ts-latex }
  else if name == "LaTeX2e" { [#ts-latex#h(0.05em)2#text(size: 0.8em)[#sym.epsilon]] }
  else if name.ends-with("LaTeX") { [#name.slice(0, name.len() - 5)#ts-latex] }
  else if name.ends-with("TeX") { [#name.slice(0, name.len() - 3)#ts-tex] }
  else { name }
}
