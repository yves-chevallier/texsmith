#set document(
title: "Font styles",
)
#set page(
paper: "a4",
margin: 2.5cm,
numbering: none,
footer: context {
if counter(page).final().first() > 1 {
align(center)[#counter(page).get().first()]
}
},
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
#text(size: 1.8em, weight: "bold")[Font styles]]
#v(1.5em)

#ts-callout-style.update("fancy")

#table(
columns: (auto, auto, auto, auto, auto, auto, 1fr),
align: (right, center, center, center, center, center, left),
table.header([\#], [i], [b], [m], [s], [c], [Exemple]),
[1], [], [], [], [], [], [The quick brown fox jumps over 012345],
[2], [x], [], [], [], [], [_The quick brown fox jumps over 012345_],
[3], [], [x], [], [], [], [*The quick brown fox jumps over 012345*],
[4], [], [], [x], [], [], [`The quick brown fox jumps over 012345`],
[5], [], [], [], [x], [], [The quick brown fox jumps over 012345],
[6], [], [], [], [], [x], [#smallcaps[The quick brown fox jumps over 012345]],
[7], [x], [x], [], [], [], [_*The quick brown fox jumps over 012345*_],
[8], [x], [], [x], [], [], [_`The quick brown fox jumps over 012345`_],
[9], [x], [], [], [x], [], [_The quick brown fox jumps over 012345_],
[10], [x], [], [], [], [x], [_#smallcaps[The quick brown fox jumps over 012345]_],
[11], [], [x], [x], [], [], [*`The quick brown fox jumps over 012345`*],
[12], [], [x], [], [x], [], [*The quick brown fox jumps over 012345*],
[13], [], [x], [], [], [x], [#smallcaps[*The quick brown fox jumps over 012345*]],
[14], [], [], [x], [x], [], [`The quick brown fox jumps over 012345`],
[15], [], [], [x], [], [x], [#smallcaps[`The quick brown fox jumps over 012345`]],
[16], [], [], [], [x], [x], [#smallcaps[The quick brown fox jumps over 012345]],
[17], [x], [x], [x], [], [], [_*`The quick brown fox jumps over 012345`*_],
[18], [x], [x], [], [x], [], [_*The quick brown fox jumps over 012345*_],
[19], [x], [x], [], [], [x], [#smallcaps[_*The quick brown fox jumps over 012345*_]],
[20], [x], [], [x], [x], [], [_`The quick brown fox jumps over 012345`_],
[21], [x], [], [x], [], [x], [#smallcaps[_`The quick brown fox jumps over 012345`_]],
[22], [x], [], [], [x], [x], [_#smallcaps[The quick brown fox jumps over 012345]_],
[23], [], [x], [x], [x], [], [*`The quick brown fox jumps over 012345`*],
[24], [], [x], [x], [], [x], [#smallcaps[*`The quick brown fox jumps over 012345`*]],
[25], [], [x], [], [x], [x], [#smallcaps[*The quick brown fox jumps over 012345*]],
[26], [], [], [x], [x], [x], [#smallcaps[`The quick brown fox jumps over 012345`]],
[27], [x], [x], [x], [x], [], [_*`The quick brown fox jumps over 012345`*_],
[28], [x], [x], [x], [], [x], [#smallcaps[_*`The quick brown fox jumps over 012345`*_]],
[29], [x], [x], [], [x], [x], [#smallcaps[_*The quick brown fox jumps over 012345*_]],
[30], [x], [], [x], [x], [x], [#smallcaps[_`The quick brown fox jumps over 012345`_]],
[31], [], [x], [x], [x], [x], [#smallcaps[*`The quick brown fox jumps over 012345`*]],
[32], [x], [x], [x], [x], [x], [#smallcaps[_*`The quick brown fox jumps over 012345`*_]],
)
