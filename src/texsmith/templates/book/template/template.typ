{# Typst scaffolding for the TeXSmith "book" template.
   Heading level 1 is styled as a chapter; mainmatter content is offset so the
   source's top-level sections become chapters (heading_offset in the writer). #}
{% if uses_mitex %}
#import "@preview/mitex:0.2.6": mi, mitex
{% endif %}
#set document(
  title: "{{ title | replace('"', '\\"') }}",
{% if author_names %}
  author: ({% for a in author_names %}"{{ a | replace('"', '\\"') }}",{% endfor %}),
{% endif %}
)
#set page(
  paper: "{{ paper | default('a5') }}",
  margin: 2cm,
  numbering: "1",
)
#set text(font: "New Computer Modern", size: 10pt, lang: "{{ language | default('en') }}")
#set par(justify: true)
#set heading(numbering: "1.1")

// Chapter-style level-1 headings: start on a fresh page with a large title.
#show heading.where(level: 1): it => [
  #pagebreak(weak: true)
  #v(2em)
  #text(size: 1.8em, weight: "bold")[#it]
  #v(1em)
]

// --- Title page ---
#align(center + horizon)[
  #text(size: 2.4em, weight: "bold")[{{ title }}]
{% if subtitle %}
  #v(0.5em)
  #text(size: 1.4em)[{{ subtitle }}]
{% endif %}
{% if author_blocks %}
  #v(2em)
{% for block in author_blocks %}
  #text(size: 1.2em)[{{ block }}]#linebreak()
{% endfor %}
{% endif %}
{% if publisher %}
  #v(1em)
  #text[{{ publisher }}]
{% endif %}
{% if edition %}
  #text(size: 0.9em)[{{ edition }}]
{% endif %}
{% if date %}
  #v(1em)
  #text[{{ date }}]
{% endif %}
]
#pagebreak()

// --- Table of contents ---
#outline()
#pagebreak()

{{ mainmatter }}

{% if listoffigures %}
#pagebreak()
#outline(title: [List of Figures], target: figure.where(kind: image))
{% endif %}
{% if listoftables %}
#pagebreak()
#outline(title: [List of Tables], target: figure.where(kind: table))
{% endif %}

{% if has_bibliography %}
#pagebreak()
#bibliography("{{ bibliography_resource }}", style: "{{ bibliography_style | default('ieee') }}")
{% endif %}
