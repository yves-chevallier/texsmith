# Extra (built-in)

Imitates the behavior of PHP Markdown Extra. These features are part of Python Markdown.

```pip
pip install markdown
```

## Abbreviations

The Abbreviations extension adds support for abbreviations in Markdown documents. An abbreviation is defined using the following syntax:

```markdown
Do you know HTML and CSS?

*[HTML]: Hyper Text Markup Language
*[CSS]: Cascading Style Sheets
```

Do you know HTML and CSS?

*[HTML]: Hyper Text Markup Language
*[CSS]: Cascading Style Sheets

## Attribute Lists

The Attribute Lists extension allows you to add attributes to various Markdown elements, such as headers, paragraphs, images, and links. You can specify attributes using curly braces `{}` immediately following the element.

```markdown
# Header 1 {#header1 .class1 key="value"}

This is a paragraph with a class and an ID.
{: #para1 .text key="value" }

![Alt text](image.jpg){#img1 .responsive width="300"}

| set on td    | set on em   |
|--------------|-------------|
| *a* { .foo } | *b*{ .foo } |
```

