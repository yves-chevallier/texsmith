#set document(
  title: "Custom Attributes",
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
  #text(size: 1.8em, weight: "bold")[Custom Attributes]
]
#v(1.5em)

These are the stalwarts borrowed from PHP Markdown Extra and bundled directly with Python-Markdown.

```
pip install markdown
```

= Attribute Lists

Attribute Lists add lightweight metadata to headings, paragraphs, images, links, and more. Drop a brace block right after the element:

```markdown
# Header 1 {#header1 .class1 key="value"}

This is a paragraph with a class and an ID.
{: #para1 .text key="value" }

![Alt text](image.jpg){#img1 .responsive width="300"}

| set on td    | set on em   |
|--------------|-------------|
| *a* { .foo } | *b*{ .foo } |
```
