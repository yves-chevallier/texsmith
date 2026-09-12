#set document(
title: "Colorful Squares",
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
#text(size: 1.8em, weight: "bold")[Colorful Squares]]
#v(1.5em)

This example shows off a custom poster-ish template with four slots wired through a local template. Front matter steers colors, slot routing, and layout—no #ts-logo("LaTeX") tweaks needed.

#figure(
image("snippet-<HASH>.png", width: 60%),
caption: [Demo],
)

The YAML front matter picks the locally defined template (`.`), sets the palette, and feeds each slot. Colors live under `colors`, and slot content under `slots`.

The manifest defines defaults, available attributes, and where they get injected.

#ts-div("tab", title: "colorful.md")[
```md
---
title: Colorful Manifesto
press:
  template: .
  colors:
    nw: "#FF5A5F"
    ne: "#FFC857"
    sw: "#30C39E"
    se: "#2D7DD2"
  slots:
    nw: Northwest
    ne: Northeast
    sw: Southwest
    se: Southeast
---
## Northwest

In the age of AI, our greatest power is not computation -- but compassion.
Let us rise above the machines we create, and redefine what it means to be human.

## Northeast

The planet is speaking through storms and silence. Climate change is our final
reminder: protect the world that protects us, before the last leaf falls.

## Southwest

We invented technology to connect souls -- not isolate them. In the glow of
progress, choose presence, choose people, choose purpose.

## Southeast

The future is not written in code or carbon. It is shaped by every act of
courage we dare today. Humanity’s masterpiece is still ahead.
```]

#ts-div("tab", title: "manifest.toml")[
```toml
[compat]
texsmith = ">=0.6,<1.0"

[latex.template]
name = "colorful-grid"
version = "0.1.0"
entrypoint = "template.tex"
engine = "lualatex"
shell_escape = false
texlive_year = 2023
tlmgr_packages = [
    "geometry",
    "fontspec",
    "xcolor",
    "pgf",
]

[latex.template.attributes.colors]
type = "mapping"
sources = ["press.colors", "colors"]

[latex.template.attributes.colors.default]
nw = "strongpink"
ne = "strongyellow"
sw = "stronggreen"
se = "strongblue"

[latex.template.slots.nw]
default = true
depth = "section"
strip_heading = true

[latex.template.slots.ne]
depth = "section"
strip_heading = true

[latex.template.slots.sw]
depth = "section"
strip_heading = true

[latex.template.slots.se]
depth = "section"
strip_heading = true

[latex.template.slots.mainmatter]
default = false

# --------------------------------------------------------------------------- #
# Typst backend: a native 2x2 colour-grid poster (parallel to the TikZ LaTeX
# template). Each quadrant is a declared slot filled from the matching section.
# --------------------------------------------------------------------------- #
[typst.template]
name = "colorful-grid"
version = "0.1.0"
entrypoint = "template.typ"

[typst.template.attributes.colors]
type = "mapping"
sources = ["press.colors", "colors"]

[typst.template.attributes.colors.default]
nw = "#FF5A5F"
ne = "#FFC857"
sw = "#30C39E"
se = "#2D7DD2"

[typst.template.slots.nw]
depth = "section"
strip_heading = true

[typst.template.slots.ne]
depth = "section"
strip_heading = true

[typst.template.slots.sw]
depth = "section"
strip_heading = true

[typst.template.slots.se]
depth = "section"
strip_heading = true

[typst.template.slots.mainmatter]
default = true
```]

#ts-div("tab", title: "template.tex")[
```tex
\documentclass{article}
\usepackage[paperwidth=20cm, paperheight=20cm, margin=0cm]{geometry}
\usepackage{fontspec}

\setsansfont{texgyreheros-regular.otf}[
    BoldFont       = texgyreheros-bold.otf,
    ItalicFont     = texgyreheros-italic.otf,
    BoldItalicFont = texgyreheros-bolditalic.otf
]
\renewcommand{\familydefault}{\sfdefault}

\usepackage{tikz}
\usetikzlibrary{calc}
\usepackage{xcolor}

\definecolor{strongpink}{RGB}{255,105,180}
\definecolor{strongyellow}{RGB}{255,215,0}
\definecolor{stronggreen}{RGB}{0,200,150}
\definecolor{strongblue}{RGB}{100,149,237}

\pagestyle{empty}

\BLOCK{ set squares = [
  {"slot": "nw", "origin": "0,0", "center": "5,5",
   "label": "NW", "content": nw, "color": colors.nw},
  {"slot": "ne", "origin": "10,0", "center": "15,5",
   "label": "NE", "content": ne, "color": colors.ne},
  {"slot": "sw", "origin": "0,10", "center": "5,15",
   "label": "SW", "content": sw, "color": colors.sw},
  {"slot": "se", "origin": "10,10", "center": "15,15",
   "label": "SE", "content": se, "color": colors.se},
] }

\begin{document}
\begin{tikzpicture}[remember picture,overlay,x=1cm,y=1cm]
  \coordinate (SW) at (current page.south west);
  \def\boxwidth{7.5cm}

  \BLOCK{ for square in squares }
  \BLOCK{ set color_name = "slotcolor-" ~ square.slot }
  \BLOCK{ set color_value = square.color | default('', true) }
  \BLOCK{ if color_value and color_value.startswith('#') }
  \definecolor{\VAR{color_name}}{HTML}{\VAR{color_value|replace('#', '')}}
  \BLOCK{ elif color_value and ',' in color_value }
  \definecolor{\VAR{color_name}}{RGB}{\VAR{color_value}}
  \BLOCK{ elif color_value }
  \colorlet{\VAR{color_name}}{\VAR{color_value}}
  \BLOCK{ else }
  \colorlet{\VAR{color_name}}{black}
  \BLOCK{ endif }

  \fill[\VAR{color_name}] ($(SW)+(\VAR{square.origin})$) rectangle ++(10,10);
  \node[text=white,font=\bfseries\Large,align=center]
  at ($(SW)+(\VAR{square.center})$)
  {\parbox{\boxwidth}{%
    \VAR{square.content|default('Slot ' ~ square.label, true)|trim}}};
  \BLOCK{ endfor }
\end{tikzpicture}
\end{document}
```]

Build it with:

```
$ ls
colorful.md  manifest.toml  template.tex
$ texsmith colorful.md -t. --build
┌───────────────┬─────────────────────────────────────┐
│ Artifact      │ Location                            │
├───────────────┼─────────────────────────────────────┤
│ PDF           │ <STEM>.pdf                        │
└───────────────┴─────────────────────────────────────┘
```
