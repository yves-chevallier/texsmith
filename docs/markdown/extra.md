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

## Definition Lists (def_list)

```markdown
Apple
:   Pomaceous fruit of plants of the genus Malus in
    the family Rosaceae.

Orange
:   The fruit of an evergreen tree of the genus Citrus.
```

Apple
:   Pomaceous fruit of plants of the genus Malus in
    the family Rosaceae.

Orange
:   The fruit of an evergreen tree of the genus Citrus.

## Fenced Code Blocks

The Fenced Code Blocks extension allows you to create code blocks using triple backticks (```) or tildes (~~~). You can also specify the programming language for syntax highlighting.

````markdown
```python { #id .foo style="color: #333" }
def hello_world():
    print("Hello, World!")
```
````

```python
def hello_world():
    print("Hello, World!")
```

## Footnotes

```markdown
Footnotes have a name, a reference[^1], and a definition[^word].

[^1]: This is a footnote definition.
[^word]: A footnote with the name "word".
```

Footnotes have a name, a reference[^1], and a definition[^word].

[^1]: A reference to a footnote definition.
[^word]: A footnote with the name "word".

## Tables

```markdown
First Header  | Second Header
------------- | -------------
Content Cell  | Content Cell
Content Cell  | Content Cell
```

## Markdown in HTML (md-in-html)

```html
<div markdown="1">
This is a *Markdown* Paragraph.
</div>
```
