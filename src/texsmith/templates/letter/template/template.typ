{# Typst scaffolding for the formal-letter template. A clean business layout:
   sender block, date, recipient, opening (the promoted leading heading), body,
   signature, and an optional postscript. Reads the nested from/to front matter
   resolved into from_name/from_address/to_name/to_address attributes. #}
{% set from_lines = (from_address or '').split('\n') %}
{% set to_lines = (to_address or '').split('\n') %}
#set page(paper: "a4", margin: 2.5cm)
#set text(font: "New Computer Modern", size: 11pt, lang: "{{ language | default('en') }}")
#set par(justify: true)

#text(size: 9pt, fill: luma(40%))[
{% if from_name %}
  #strong[{{ from_name | te }}]#linebreak()
{% endif %}
{% for line in from_lines if line.strip() %}
  {{ line | te }}{% if not loop.last %}#linebreak(){% endif %}

{% endfor %}
]

#v(1.2em)
#align(right)[{{ date | longdate | te }}]
#v(0.6em)

{% if to_name %}
{{ to_name | te }}#linebreak()
{% endif %}
{% for line in to_lines if line.strip() %}
{{ line | te }}{% if not loop.last %}#linebreak(){% endif %}

{% endfor %}

#v(2em)

{% if title %}
{{ title | te }},
{% endif %}

#v(0.4em)

{{ mainmatter }}

#v(1.4em)

{% set signature_image = asset(signature) %}
{% if signature_image %}
#image("{{ signature_image }}", height: 1.6cm)

{% endif %}
{% if from_name %}
{{ from_name | te }}
{% endif %}

{% if postscript %}
#v(1em)
#emph[PS: {{ postscript | te }}]
{% endif %}
