#set page(width: 20cm, height: 20cm, margin: 0pt)
#set text(font: ("TeX Gyre Heros", "Helvetica", "Arial"), fill: white, weight: "bold")
#set par(justify: false)

#let quadrant(fill, body) = rect(
width: 10cm,
height: 10cm,
fill: fill,
stroke: none,
inset: 1.25cm,
)[#align(center + horizon)[#text(size: 14.4pt)[#body]]]

#grid(
columns: (10cm, 10cm),
rows: (10cm, 10cm),
column-gutter: 0pt,
row-gutter: 0pt,
quadrant(rgb("#FF5A5F"), [In the age of AI, our greatest power is not computation – but compassion.
Let us rise above the machines we create, and redefine what it means to be human.]),
quadrant(rgb("#FFC857"), [The planet is speaking through storms and silence. Climate change is our final
reminder: protect the world that protects us, before the last leaf falls.]),
quadrant(rgb("#30C39E"), [We invented technology to connect souls – not isolate them. In the glow of
progress, choose presence, choose people, choose purpose.]),
quadrant(rgb("#2D7DD2"), [The future is not written in code or carbon. It is shaped by every act of
courage we dare today. Humanity’s masterpiece is still ahead.]),
)
