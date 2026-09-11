#set document(
  title: "Emoji Support",
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
#set page(columns: 2)
#set heading(numbering: "1.1")

#align(center)[
  #text(size: 1.8em, weight: "bold")[Emoji Support]
]
#v(1.5em)

= Introduction

TeXSmith renders emoji as glyphs when you pick a font flavour:

```yaml
press:
  fonts:
    emoji: black
```

You can choose among four built-in options:

/ `black`: OpenMoji Black (default).
/ `color`: Noto Color Emoji.
/ `twemoji`: Use the `twemoji` package as fallback.
/ `artifact`: Download emoji as images using Twemoji.

Any other name is treated as a custom font family to load directly.

Engines:

- LuaLaTeX relies on `luaotfload` to add the emoji font as a fallback.
- XeLaTeX/Tectonic use `ucharclasses` to automatically switch to the emoji font on the U+1F000–U+1FAFF range.
  You can type emoji directly in Markdown or LaTeX source.

= Examples

#table(
  columns: 2,
  align: (left, left),
  table.header([Emoji], [Description]),
  [😊], [Smiling face with smiling eyes],
  [🚀], [Rocket],
  [🍕], [Pizza],
  [🎉], [Party popper],
  [🐍], [Snake],
  [🌍], [Globe showing Europe-Africa],
  [💻], [Laptop computer],
  [📚], [Books],
  [🎨], [Artist palette],
  [👽], [Alien],
  [👋], [Waving hand],
  [🤖], [Robot],
  [🦄], [Unicorn],
  [🧠], [Brain],
  [🛸], [Flying saucer],
  [🛰️], [Satellite],
  [🐙], [Octopus],
  [📝], [Memo],
  [📋], [Note],
  [⭐], [Star],
  [✅], [Check mark],
  [❌], [Cross mark],
  [🧪], [Experiment],
  [💡], [Light Bulb],
)
