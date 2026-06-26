{# Typst scaffolding for the TeXSmith "article" template.
   Rendered with standard Jinja delimiters; the document body (mainmatter /
   abstract) is produced by TypstWriter. #}
{% if uses_mitex %}
#import "@preview/mitex:0.2.6": mi, mitex
{% endif %}
#set document(
  title: "{{ title | replace('"', '\\"') }}",
{% if authors %}
  author: ({% for a in author_names %}"{{ a | replace('"', '\\"') }}",{% endfor %}),
{% endif %}
)
#set page(
  paper: "{{ paper | default('a4') }}",
  margin: 2.5cm,
{% if not page_numbers | default(true) %}
  numbering: none,
{% else %}
  numbering: "1",
{% endif %}
)
#set text(font: "New Computer Modern", size: 11pt, lang: "{{ language | default('en') }}")
#set par(justify: true)
{% if uses_eqnref %}
#set math.equation(numbering: "(1)")
{% endif %}
{% if columns | default(1) | int > 1 %}
#set page(columns: {{ columns | int }})
{% endif %}
{% if numbering | default(true) %}
#set heading(numbering: "1.1")
{% else %}
#set heading(numbering: none)
{% endif %}

{% if title %}
#align(center)[
  #text(size: 1.8em, weight: "bold")[{{ title }}]
{% if subtitle %}
  #linebreak()
  #text(size: 1.2em)[{{ subtitle }}]
{% endif %}
]
{% if author_blocks %}
#align(center)[
{% for block in author_blocks %}
  {{ block }}{% if not loop.last %} #h(1.5em) {% endif %}
{% endfor %}
]
{% endif %}
{% if date or version %}
#align(center)[{% if date %}{{ date }}{% endif %}{% if version %} #h(0.5em) #text(size: 0.9em)[{{ version }}]{% endif %}]
{% endif %}
#v(1.5em)
{% endif %}

{% if abstract %}
#block(width: 100%, inset: (x: 2em))[
  #align(center)[#text(weight: "bold")[Abstract]]
  #v(0.5em)
{{ abstract }}
]
#v(1em)
{% endif %}

{% if toc %}
#outline()
#v(1em)
{% endif %}

{{ mainmatter }}

{% if has_bibliography %}
#bibliography("{{ bibliography_resource }}", style: "{{ bibliography_style | default('ieee') }}")
{% endif %}
