# Custom Attributes

These are the stalwarts borrowed from PHP Markdown Extra and bundled directly with Python-Markdown.

```pip
pip install markdown
```

## Attribute Lists

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
