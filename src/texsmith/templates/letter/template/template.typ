{# Typst scaffolding for the formal-letter template: the window-envelope
   layouts of DIN 5008 (Germany), SN 010130 (Switzerland) and NF Z 11-001
   (France), with the measures KOMA-Script's DIN / SN / NF letter-class
   options carry, so the LaTeX and the Typst letter fold into the same
   envelope. `format` picks the standard, `fold_marks` adds the marks. #}
{% set standard = (format or 'din') | lower %}
{% if standard == 'sn' %}
{% set win = {'x': 112, 'y': 45, 'w': 90, 'h': 45, 'indent': 0, 'ref': 98.5, 'head_y': 8, 'head_w': 194, 'fold': [105, 210]} %}
{% elif standard == 'nf' %}
{% set win = {'x': 100, 'y': 35, 'w': 100, 'h': 45, 'indent': 10, 'ref': 99, 'head_y': 15, 'head_w': 170, 'fold': [99, 198]} %}
{% else %}
{% set win = {'x': 20, 'y': 45, 'w': 85, 'h': 45, 'indent': 0, 'ref': 98.5, 'head_y': 8, 'head_w': 170, 'fold': [105, 210]} %}
{% endif %}
{% set margin = {'left': 25, 'right': 20, 'top': 25, 'bottom': 25} %}
{% set from_lines = (from_address or '').split('\n') | map('trim') | reject('equalto', '') | list %}
{% set to_lines = (to_address or '').split('\n') | map('trim') | reject('equalto', '') | list %}
{% set back_lines = (back_address or '').split('\n') | map('trim') | reject('equalto', '') | list %}
#set page(
  paper: "a4",
  margin: (left: {{ margin.left }}mm, right: {{ margin.right }}mm, top: {{ margin.top }}mm, bottom: {{ margin.bottom }}mm),
{% if page_numbers %}
  numbering: "1",
{% endif %}
)
#set text(font: "New Computer Modern", size: 11pt, lang: "{{ language | default('en') }}")
#set par(justify: true)

// The first page is laid out from the page's top-left corner: the sender's
// head, the address window with the return address on its top line, the
// date on the reference line, and the fold marks on the left edge.
#let at(x, y, body) = place(top + left, dx: x - {{ margin.left }}mm, dy: y - {{ margin.top }}mm, body)

#at({{ (210 - win.head_w) / 2 }}mm, {{ win.head_y }}mm, block(width: {{ win.head_w }}mm, text(size: 10pt)[
{% if from_name %}
  {{ from_name | te }}{% if from_lines %}\{% endif %}

{% endif %}
{% for line in from_lines %}
  {{ line | te }}{% if not loop.last %}\{% endif %}

{% endfor %}
]))

#at({{ win.x }}mm, {{ win.y }}mm, block(width: {{ win.w }}mm, height: {{ win.h }}mm, inset: (left: {{ win.indent }}mm))[
  #block(width: 100%, height: 5mm, align(bottom + left, text(size: 7pt)[
{% if back_lines %}
    #underline[{{ back_lines | map('te') | join(', ') }}]
{% elif from_name %}
    #underline[{{ ([from_name] + from_lines) | map('te') | join(', ') }}]
{% endif %}
  ]))
  #v(2.5mm)
{% if to_name %}
  {{ to_name | te }}{% if to_lines %}\{% endif %}

{% endif %}
{% for line in to_lines %}
  {{ line | te }}{% if not loop.last %}\{% endif %}

{% endfor %}
])

#place(top + right, dy: {{ win.ref }}mm - {{ margin.top }}mm, [{{ date | longdate | te }}])

{% if fold_marks %}
{% for y in win.fold %}
#at(3.5mm, {{ y }}mm, line(length: 4mm, stroke: 0.3pt))
{% endfor %}
#at(3.5mm, 148.5mm, line(length: 6mm, stroke: 0.3pt))
{% endif %}

// The body starts two lines under the reference line.
#v({{ win.ref + 10 - margin.top }}mm)

{% if object %}
*{{ object | te }}*

{% endif %}
{% if title %}
{{ title | te }}

{% endif %}
{{ mainmatter }}

{% if closing %}
#v(0.5em)
{{ closing | te }}
{% endif %}

#v(0.8em)
{% set signature_image = asset(signature) %}
{% if signature_image %}
#image("{{ signature_image }}", height: 1.6cm)

{% endif %}
{% if from_name %}
{{ from_name | te }}
{% endif %}

{% if postscript %}
#v(1em)
PS: {{ postscript | te }}
{% endif %}
