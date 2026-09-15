// texsmith.typ — the Typst mirror of the LaTeX fragment contracts
// (specs/migration/fragment-contracts.md §1, §3 rule 7). One hyphenated
// function per contract; named arguments mirror the LaTeX keys, the content
// comes last. The tmark Typst writer emits these calls; this file is inlined
// ahead of the body and a template restyles a construct after it, either by
// redefining the function with the same signature or through the states
// below (`#ts-callout-style.update("classic")`).

// palette

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

// The icons of texsmith.core.callouts.DEFAULT_CALLOUTS, one per kind.
#let ts-callout-icons = (
  note: "📝", abstract: "📄", summary: "📋", info: "ℹ", seealso: "ℹ",
  tip: "⭐", hint: "💡", success: "✅", question: "❓", warning: "⚠",
  caution: "🚧", failure: "❗", danger: "🔥", important: "❗", bug: "🐞",
  example: "🧪", quote: "✒", default: "🎤",
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

// The emoji fonts, colour first (`ts-emoji`) or monochrome first (icons of
// the classic callouts). Typst falls back along the list.
#let ts-emoji-fonts = ("Noto Color Emoji", "OpenMoji")
#let ts-emoji-fonts-black = ("OpenMoji", "Noto Color Emoji")

// ts-typesetting

// Lead-in of a paragraph (Para.lead): a run-in bold line.
#let ts-lead(body) = block(above: 0.6em, below: 0.3em, strong(body))

// Highlight is native (#highlight); kept for symmetry with \tsmark.
#let ts-mark(body) = highlight(body)

// A thematic break at the top level of the document: paged output turns the
// page (decisions X2).
#let ts-divider() = pagebreak(weak: true)

// The same thematic break inside a container (quote, callout, figure, div,
// list item, cell, aside, note): a separator, never a page break — Typst
// rejects a page break inside a container outright (challenge C48).
#let ts-rule() = block(
  width: 100%,
  above: 0.8em,
  below: 0.8em,
  line(length: 100%, stroke: 0.4pt + luma(60%)),
)

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

// The page margin on `side` ("left" / "right"), whatever form `page.margin`
// took: a length, a dictionary, or `auto` (Typst's default, 2.5/21 of the
// shorter page side). Read in a `context`.
#let ts-page-margin(side) = {
  let margin = page.margin
  let fallback = 2.5 / 21 * calc.min(page.width, page.height)
  let pick(value) = if value == auto { fallback } else { value }
  if type(margin) == dictionary {
    pick(margin.at(side, default: margin.at("x", default: margin.at("rest", default: auto))))
  } else {
    pick(margin)
  }
}

// #ts-aside(side: "left")[body]: a margin note. Inline — a zero-width box,
// so the paragraph flows on — placed in the margin next to the line that
// carries it; `left` / `inner` reverse the side.
#let ts-aside(side: "right", body) = box(width: 0pt, height: 0pt, context {
  let gap = 0.35cm
  let position = here().position()
  let note = text(size: 0.75em, body)
  if side == "left" or side == "inner" {
    let margin = ts-page-margin("left")
    place(
      top + left, dx: gap - position.x, dy: -0.8em,
      block(width: margin - 2 * gap, align(right, note)),
    )
  } else {
    let margin = ts-page-margin("right")
    place(
      top + left, dx: page.width - margin + gap - position.x, dy: -0.8em,
      block(width: margin - 2 * gap, align(left, note)),
    )
  }
})

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

// tables

// Every table is set the way `booktabs` sets the LaTeX ones: no vertical
// rules, a rule above and below the table and a thinner one under the
// header row. The writer only passes `columns`, `align` and the cells.
#set table(
  stroke: (x, y) => if y == 0 { (bottom: 0.4pt + black) } else { none },
  inset: (x: 0.6em, y: 0.35em),
)
#show table: it => block(
  width: auto,
  inset: 0pt,
  stroke: (top: 0.8pt + black, bottom: 0.8pt + black),
  it,
)

// ts-callouts

// The style of every callout — `fancy` (coloured frame, icon), `classic`
// (a rule on the left, monochrome icon) or `minimal` (a thin frame, no
// icon) — mirrors the LaTeX `callouts.style` attribute. A template picks it
// after the prelude: `#ts-callout-style.update("classic")`.
#let ts-callout-style = state("ts-callout-style", "fancy")

#let ts-callout-icon(kind, fonts) = text(
  font: fonts, size: 0.95em, ts-callout-icons.at(kind, default: ts-callout-icons.default),
)

#let ts-callout-fancy(kind, colors, heading, body) = block(
  width: 100%,
  stroke: (left: 1.5mm + colors.frame, rest: 0.4pt + colors.frame),
  radius: (right: 2pt),
  // Half the strokes sit inside the block: keep the fills off them.
  inset: (left: 0.75mm, right: 0.2pt, top: 0.2pt, bottom: 0.2pt),
  breakable: true,
  above: 1em,
  below: 1em,
  stack(
    dir: ttb,
    block(
      width: 100%, fill: colors.frame.lighten(93%), inset: (x: 0.7em, y: 0.4em),
      [#ts-callout-icon(kind, ts-emoji-fonts)#h(0.5em)#text(
        weight: "bold", font: "DejaVu Sans", size: 0.9em, fill: colors.frame, heading,
      )],
    ),
    block(width: 100%, inset: (x: 0.7em, top: 0.5em, bottom: 0.6em), body),
  ),
)

#let ts-callout-classic(kind, colors, heading, body) = block(
  width: 100%,
  stroke: (left: 1mm + luma(40%)),
  inset: (left: 0.5mm + 0.7em, right: 0.3em, top: 0.3em, bottom: 0.4em),
  breakable: true,
  above: 1em,
  below: 1em,
  stack(
    dir: ttb,
    spacing: 0.45em,
    [#ts-callout-icon(kind, ts-emoji-fonts-black)#h(0.5em)#text(weight: "bold", fill: luma(20%), heading)],
    body,
  ),
)

#let ts-callout-minimal(kind, colors, heading, body) = block(
  width: 100%,
  stroke: 0.3mm + black,
  radius: 0.4mm,
  inset: (rest: 0.15mm),
  breakable: true,
  above: 1em,
  below: 1em,
  stack(
    dir: ttb,
    block(
      width: 100%, inset: (x: 0.6em, y: 0.3em), stroke: (bottom: 0.2mm + black),
      text(weight: "bold", heading),
    ),
    block(width: 100%, inset: (x: 0.6em, top: 0.45em, bottom: 0.5em), body),
  ),
)

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
  let content = context {
    let style = ts-callout-style.get()
    if style == "classic" {
      ts-callout-classic(key, colors, heading, body)
    } else if style == "minimal" {
      ts-callout-minimal(key, colors, heading, body)
    } else {
      ts-callout-fancy(key, colors, heading, body)
    }
  }
  if id != none [#content #label(id)] else { content }
}

// ts-code

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

// ts-keystrokes

// #ts-keys("Ctrl", "Alt", "Del")
#let ts-keys(..keys) = {
  let boxes = keys.pos().map(k => box(
    stroke: 0.5pt + luma(60), fill: luma(240), radius: 1.5pt,
    inset: (x: 0.4em, y: 0.15em), baseline: 0.15em,
    text(size: 0.8em, font: "DejaVu Sans", k),
  ))
  boxes.join([ + ])
}

// ts-todolist

// #ts-task("done")[body]
#let ts-task(state, body) = {
  let mark = if state == "done" { "☑" } else if state == "partial" { "◪" } else { "☐" }
  [#mark #body]
}

// ts-glossary

#let ts-gls(key) = key
#let ts-acr(key) = key

// ts-index

// The plain text of `it` (a string or content), for sorting index entries.
#let ts-plain(it) = {
  if type(it) == str { it }
  else if type(it) == content {
    if it.has("text") { it.text }
    else if it.has("children") { it.children.map(ts-plain).join("") }
    else if it.has("body") { ts-plain(it.body) }
    else if it.func() == smartquote { "'" }
    else { "" }
  }
  else { repr(it) }
}

// #ts-index([a], [b], registry: "r", main: true): an entry of the index —
// `[a]` a term, `[a], [b]` the sub-entry `b` of `a`. It leaves no ink; the
// page it sits on is what `ts-print-index` reports.
#let ts-index(..path, registry: none, main: false) = {
  let parts = path.pos()
  [#metadata((
    path: parts, plain: parts.map(ts-plain), registry: registry, main: main,
  )) <ts-index-entry>]
}

// #ts-print-index(title: [Index], registry: none): the index of a registry
// (`none` is the default registry), the terms sorted, a sub-entry under its
// parent, the page numbers of each term in order.
#let ts-print-index(title: [Index], registry: none) = context {
  let entries = query(<ts-index-entry>)
  let groups = (:)
  for entry in entries {
    let value = entry.value
    if value.registry != registry { continue }
    let page = counter(page).at(entry.location()).first()
    // A sub-entry lists its parents too, without a page: `apple` above `Fuji`.
    for depth in range(1, value.path.len() + 1) {
      let key = value.plain.slice(0, depth).map(lower).join("\u{1}")
      let own = depth == value.path.len()
      if key not in groups {
        groups.insert(key, (path: value.path.slice(0, depth), pages: ()))
      }
      if own and page not in groups.at(key).pages { groups.at(key).pages.push(page) }
    }
  }
  if groups.len() == 0 { return }
  heading(level: 1, numbering: none, title)
  columns(2, {
    set par(hanging-indent: 1em, first-line-indent: 0em)
    for key in groups.keys().sorted() {
      let group = groups.at(key)
      let depth = group.path.len() - 1
      let pages = if group.pages.len() > 0 [, #group.pages.map(str).join(", ")] else []
      block(
        inset: (left: depth * 1em), above: 0.35em, below: 0.35em,
        [#group.path.last()#pages],
      )
    }
  })
}

// ts-bibliography

// #ts-page(<label>): the page number of a label (textual references).
#let ts-page(target) = context { counter(page).at(target).first() }

// ts-fonts

#let ts-script(slug, body) = body
#let ts-emoji(body) = text(font: ts-emoji-fonts, body)

// ts-critic

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

// subfigures

// The images of a `::: figure` are subfigures (spec §Captions and floats,
// challenge C43): they carry no number of the `fig` series, and a reference
// to one reads the container's number plus a letter. Kept identical to
// `tmark-writers/assets/texsmith.typ`, the file the writers are written
// against; the duplication is tracked in specs/migration/status.md.

#let ts-subfigure(body, caption: none) = figure(
  body,
  caption: caption,
  kind: "ts-subfigure",
  supplement: none,
  numbering: "(a)",
)

// `#ts-subnumber(<fig:left>)`: what a reference to a sub-figure shows —
// the enclosing figure's number and the sub-figure's letter, read at the
// sub-figure's own location (the two counters are separate, so `#ref`
// alone would show the letter only).
#let ts-subnumber(target) = context {
  let matches = query(target)
  if matches.len() > 0 {
    let loc = matches.first().location()
    numbering("1", ..counter(figure.where(kind: image)).at(loc))
    numbering("a", ..counter(figure.where(kind: "ts-subfigure")).at(loc))
  }
}
