#set document(
  title: "Limitations",
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
  #text(size: 1.8em, weight: "bold")[Limitations]
]
#v(1.5em)

= Highlighting with `ucharclasses`

The `ucharclasses` package allows you to define font transitions based on Unicode character classes. However, when using it in combination with the `soul` package for highlighting, there can be compatibility issues. For example, the following code may not work as expected:

```latex
\documentclass{article}
\usepackage{soul}
\usepackage{fontspec}
\usepackage[Latin]{ucharclasses}

\setmainfont{Latin Modern Roman}
\setDefaultTransitions{\rmfamily}{\rmfamily}
\enableTransitionRules
\AtBeginDocument{\enableTransitionRules}

\begin{document}
\hl{Foobar}
\end{document}
```

TeXSmith is meant to be compatible with XeLaTeX and LuaLaTeX, but due to the way `ucharclasses` handles font transitions, it may interfere with the highlighting functionality provided by `soul`. When TeXSmith detects XeLaTeX it now disables `soul` and falls back to a plain yellow `\hl{...}` (no box). With LuaLaTeX it loads `lua-ul` instead of `soul`, keeping underlines without tripping over `ucharclasses`. Output therefore differs slightly between XeLaTeX and LuaLaTeX, but both builds succeed.
