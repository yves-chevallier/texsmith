{# Typst scaffolding for the "colorful-grid" poster template.
   A 20x20cm page split into a 2x2 colour grid; each quadrant's text comes from
   the matching section (nw / ne / sw / se slots). Parallel to template.tex. #}
{% macro tcolor(value, fallback) -%}
{%- if value and value.startswith('#') -%}rgb("{{ value }}")
{%- elif value and ',' in value -%}rgb({{ value }})
{%- elif value -%}rgb("{{ fallback }}")
{%- else -%}rgb("{{ fallback }}")
{%- endif -%}
{%- endmacro -%}
#set page(width: 20cm, height: 20cm, margin: 0pt)
#set text(font: ("TeX Gyre Heros", "Helvetica", "Arial"), fill: white, weight: "bold")
#set par(justify: false)

#let quadrant(fill, body) = rect(
  width: 10cm,
  height: 10cm,
  fill: fill,
  stroke: none,
  inset: 1.5cm,
)[#align(center + horizon)[#text(size: 20pt)[#body]]]

#grid(
  columns: (10cm, 10cm),
  rows: (10cm, 10cm),
  column-gutter: 0pt,
  row-gutter: 0pt,
  quadrant({{ tcolor(colors.nw, 'FF5A5F') }}, [{{ nw }}]),
  quadrant({{ tcolor(colors.ne, 'FFC857') }}, [{{ ne }}]),
  quadrant({{ tcolor(colors.sw, '30C39E') }}, [{{ sw }}]),
  quadrant({{ tcolor(colors.se, '2D7DD2') }}, [{{ se }}]),
)
