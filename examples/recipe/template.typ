{# Typst recipe card — data-driven, mirroring template.tex: it renders the
   structured YAML front matter (title / time / sections / steps) directly,
   not the (empty) document body. TikZ cooking symbols have no Typst
   counterpart, so the time box uses plain labels. #}
{% set recipe = front_matter %}
{% set time = recipe.time | default({}, true) %}
{% macro quantity(value) -%}
{%- if value is mapping -%}
{%- if value.text -%}{{ value.text | te }}
{%- elif value.amount is defined -%}{{ value.amount | te }}{% if value.unit %} {{ value.unit | te }}{% endif %}
{%- endif -%}
{%- elif value is number -%}{{ value | te }}
{%- elif value -%}{{ value | te }}
{%- endif -%}
{%- endmacro -%}
{% macro notecell(instructions) -%}
{%- for instruction in instructions -%}{{ instruction | te }}{% if not loop.last %} #linebreak() {% endif %}{%- endfor -%}
{%- endmacro -%}
#set page(paper: "a4", margin: (top: 2cm, left: 2cm, right: 2cm, bottom: 1cm))
#set text(font: ("TeX Gyre Heros", "Helvetica", "Arial"), size: 10pt)
#set par(justify: true)

#text(size: 2.2em, weight: "bold")[{{ recipe.title | default('Recette', true) | te }}]
#v(0.8cm)

#grid(
  columns: (3fr, 7fr),
  column-gutter: 1cm,
  [
    #line(length: 100%, stroke: 1.5pt)
    #v(0.2em)
    *Temps total* — *{{ time.total | default('--', true) | te }}* min #linebreak()
    *Préparation* — *{{ time.preparation | default('--', true) | te }}* min #linebreak()
    *Cuisson* — *{{ time.cooking | default('--', true) | te }}* min
    #v(0.2em)
    #line(length: 100%, stroke: 1.5pt)

    {% if recipe.description %}
    #v(0.6em)
    #text(weight: "bold", size: 1.1em)[Description]

    {{ recipe.description | te }}
    {% endif %}

    #v(0.6em)
    #text(weight: "bold", size: 1.1em)[Conseils]

    {{ recipe.notes | default('Aucun conseil enregistré.', true) | te }}
  ],
  [
    {% for section in recipe.sections | default([], true) %}
    #text(weight: "bold", size: 1.1em)[{{ section.title | default('Étape', true) | te }}]
    #v(0.4em)
    {% if section.instructions %}
    {% for instruction in section.instructions %}
    - {{ instruction | te }}
    {% endfor %}
    {% endif %}
    {% if section.steps %}
    #table(
      columns: (auto, auto, 1fr),
      stroke: (y: 0.3pt),
      inset: (x: 4pt, y: 6pt),
      align: (left + top, left + top, left + top),
      {% for step in section.steps %}
      {% set raw = step.ingredients | default([], true) %}
      {% if raw is mapping %}{% set ingredients = [raw] %}{% elif raw is iterable and raw is not string %}{% set ingredients = raw %}{% else %}{% set ingredients = [] %}{% endif %}
      {% set note = step.instructions | default([], true) %}
      {% if ingredients %}
      {% for ingredient in ingredients %}
      [{{ quantity(ingredient.quantity | default('', true)) }}], [{{ ingredient.name | default('', true) | te }}], [{% if loop.first %}{{ notecell(note) }}{% endif %}],
      {% endfor %}
      {% else %}
      [], [], [{{ notecell(note) }}],
      {% endif %}
      {% endfor %}
    )
    {% endif %}
    #v(0.8em)
    {% endfor %}
  ],
)
