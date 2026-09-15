---
press:
  author: Yves Chevallier
  description: "Overview of the TMark syntax and how TeXSmith typesets it."
  keywords: ["TMark", "Markdown", "syntax", "cheatsheet"]
  slots:
    abstract: Abstract
  toc: true
  override:
    preamble: |
        \usepackage{xcolor}
        \renewenvironment{displayquote}
        {%
            \begin{tcolorbox}[
            enhanced, breakable, colback=gray!10,
            boxrule=0pt,
            borderline west={3pt}{0pt}{gray!70},
            left=6pt, right=6pt, top=6pt, bottom=6pt]%
        }
        { \end{tcolorbox} }
---
# TMark Syntax

## Abstract

TMark is the Markdown dialect TeXSmith reads: CommonMark, the extensions authors already know from GitHub and MkDocs, and a small closed set of constructs for print — roles such as `{index}[term]`, containers such as `::: note`, data fences such as `yaml table`. This document walks through the syntax construct by construct, each one shown as source and as the typeset result. It doubles as a test sheet for templates.

## Structure

### Headings

Six heading levels, `#` to `######`. LaTeX has fewer sectioning commands (`\section`, `\subsection`, `\subsubsection`, `\paragraph`, `\subparagraph`), so the deepest levels become run-in bold headings.

```md
# Heading 1

Lorem ipsum dolor sit amet.

## Heading 2

Lorem ipsum dolor sit amet.

### Heading 3

Lorem ipsum dolor sit amet.

#### Heading 4

Lorem ipsum dolor sit amet.

##### Heading 5

Lorem ipsum dolor sit amet.
```

### Bold

Strong emphasis with `**`, typeset as `\textbf{…}`.

```md
**text** or **t**ex**t**
```

> **text** or **t**ex**t**

### Italic

Emphasis with `*` or `_`, for terminology or voice.

```md
This _text_ or *text* is italic.
```

> This _text_ or *text* is italic.

### Nested emphasis

Bold and italic combine in either spelling.

```md
**_bold and italic_**

***bold and italic***
```

> **_bold and italic_**
>
> ***bold and italic***

### Small capitals

In CommonMark `**` and `__` both mean bold. TMark keeps `**` for bold and reads `__` as small capitals.

```md
This is __small capitals__.
```

> This is __small capitals__.

### Strikethrough

Marks text as deleted or obsolete.

```md
We ~~do not~~ want this.
```

> We ~~do not~~ want this.

### Underline

The `{underline}` role underlines text. PyMdownX's `^^text^^` spells the same
node, but only with the `inline.insert` feature enabled; without it the carets
are literal.

```md
{underline}[text]
```

> {underline}[text]

### Highlight

`==text==` highlights a run of text, as a marker would.

```md
==Cellular respiration is a set of metabolic reactions== that take place
in the cells of organisms. Its ==primary== function is to convert
biochemical energy from nutrients into ==adenosine triphosphate (ATP)==,
and then release waste products.
```

> ==Cellular respiration is a set of metabolic reactions== that take place in the
> cells of organisms. Its ==primary== function is to convert biochemical energy
> from nutrients into ==adenosine triphosphate (ATP)==, and then release waste
> products.

### Subscript and superscript

`~…~` lowers, `^…^` raises. Unicode subscripts and superscripts pass through.

```md
H~2~O, E = mc^2^

H₂O, E = mc²
```

> H~2~O, E = mc^2^
>
> H₂O, E = mc²

### Smart punctuation

Straight quotes become typographic quotes, three dots an ellipsis, `--` an en dash and `---` an em dash. A `---` alone on its line is a thematic break, not a dash.

```md
"Smart quotes", ellipses..., en-dash --, em-dash ---

Achilles -- the swiftest runner -- was fast, but not as fast as the tortoise.
```

> "Smart quotes", ellipses..., en-dash –, em-dash —
>
> Achilles -- the swiftest runner -- was fast, but not as fast as the tortoise.

### Inline code and code blocks

````md
This entry is `inline code`, or can be in a fenced code block:

```python
print("Hello")
```
````

> This entry is `inline code`, or can be in a fenced code block:
>
> ```python
> print("Hello")
> ```

### Links

External links become clickable links in the PDF. A bare URL is linked as it stands.

```md
The German-born physicist [Albert Einstein](https://en.wikipedia.org/wiki/Albert_Einstein) is famous for
his Nobel prize and the theory of relativity: https://en.wikipedia.org/wiki/Theory_of_relativity
```

> The German-born physicist [Albert Einstein](https://en.wikipedia.org/wiki/Albert_Einstein) is famous for
> his Nobel prize and the theory of relativity: https://en.wikipedia.org/wiki/Theory_of_relativity

### Images

Local or remote images; a remote one is fetched at build time.

```md
![Random Picture](https://picsum.photos/500/200)
```

> ![Random Picture](https://picsum.photos/500/200)

### Bulleted lists

```md
- First
- Second
    - Subitem
```

> - First
> - Second
>     - Subitem

### Numbered lists

```md
1. Numbered first
2. Numbered second
    1. Sub-numbered
        a. Sub-sub-numbered
        b. Sub-sub-numbered
    2. Sub-numbered
```

> 1. Numbered first
> 2. Numbered second
>     1. Sub-numbered
>         a. Sub-sub-numbered
>         b. Sub-sub-numbered
>     2. Sub-numbered

### Task lists

```md
- [x] Done
- [ ] To do
```

> - [x] Done
> - [ ] To do

### Definition lists

A term, then its definition on a `:` line.

```md
Term
: Definition of the term

Another term
:   Another definition with a longer description that spans
    multiple lines and
    is indented properly.
```

> Term
> : Definition of the term
>
> Another term
> :   Another definition with a longer description that spans
>     multiple lines and
>     is indented properly.

### Block quotes

```md
> Quote
```

> Quote

### Thematic breaks

A `---` on its own line. At the top level of a paged document it turns the page; inside a container it draws a rule.

```md
---
```

> ---

## Blocks

### Tables

Pipe tables for plain 2-D data; a `yaml table` fence for spans, grouped headers and footers (see the `tables` example).

```md
| Column 1 | Column 2 |
| -------- | -------- |
| Value 1  | Value 2  |
| Value 3  | Value 4  |
```

> | Column 1 | Column 2 |
> | -------- | -------- |
> | Value 1  | Value 2  |
> | Value 3  | Value 4  |

### Footnotes

A footnote is a note placed at the bottom of the page.

```md
Text with note[^1].

[^1]: Here is the note.
```

> Text with note[^1].
>
> [^1]: Here is the note.

### Abbreviations

An abbreviation definition expands its first occurrence and lists the acronym in the backmatter.

```md
The HTML standard.

*[HTML]: HyperText Markup Language
```

> The HTML standard.
>
> *[HTML]: HyperText Markup Language

### Callouts

A `::: kind` container is a callout: note, tip, warning, danger, and the other kinds of the callout palette. Attributes follow the kind. PyMdownX's `!!! note` and `??? warning` spell the same containers.

```md
::: note
This is a note.
:::

::: warning {collapsed=true}
This is a warning.
:::
```

`collapsed=true` creates a collapsible block in HTML output only.

::: note
This is a note.
:::

::: warning {collapsed=true}
This is a warning.
:::

A title of its own:

```md
::: note {title=Title collapsed=false}
Collapsible content.
:::
```

> ::: note {title=Title collapsed=false}
> Collapsible content.
> :::

### Tabs

A `tabs` container holds one `tab` container per pane. Paged output lays the panes one after the other, each under its title.

````md
:::: tabs
::: tab {title=Windows}
Windows is a Microsoft operating system.
:::
::: tab {title=Linux}
Linux is an open-source operating system.
:::
::::
````

:::: tabs
::: tab {title=Windows}
Windows is a Microsoft operating system.
:::
::: tab {title=Linux}
Linux is an open-source operating system.
:::
::::

### Diagrams

A `mermaid` fence is rendered to a vector image at build time; `image` on the fence makes it a figure, with the attributes an image takes.

````md
```mermaid image width="20%"
graph TD;
  A-->B;
```
````

> ```mermaid image width="20%"
> graph TD;
>   A-->B;
> ```

### Math

Inline math between `$…$`, display math between `$$…$$`, in LaTeX syntax on both backends.

```md
The differential form of Maxwell's equations:

$$
\begin{aligned}
\nabla \cdot \mathbf{E} &= \frac{\rho}{\varepsilon_0} \\
\nabla \cdot \mathbf{B} &= 0 \\
\nabla \times \mathbf{E} &= -\frac{\partial \mathbf{B}}{\partial t} \\
\nabla \times \mathbf{B} &= \mu_0 \mathbf{J} + \mu_0 \varepsilon_0
\frac{\partial \mathbf{E}}{\partial t}
\end{aligned}
$$
```

> The differential form of Maxwell's equations:
>
> $$
> \begin{aligned}
> \nabla \cdot \mathbf{E} &= \frac{\rho}{\varepsilon_0} \\
> \nabla \cdot \mathbf{B} &= 0 \\
> \nabla \times \mathbf{E} &= -\frac{\partial \mathbf{B}}{\partial t} \\
> \nabla \times \mathbf{B} &= \mu_0 \mathbf{J} + \mu_0 \varepsilon_0
> \frac{\partial \mathbf{E}}{\partial t}
> \end{aligned}
> $$

### Raw passthrough

A `latex raw` fence is written to the LaTeX output verbatim; the `{raw latex}(…)` role does the same inside a paragraph. Neither reaches the other backends.

````md
```latex raw
\clearpage
```
````

```latex raw
\clearpage
```

Inline variant:

```md
Insert... {raw latex}(\clearpage) anywhere in the paragraph.
```

Insert... {raw latex}(\clearpage) anywhere in the paragraph.

### Including a file

A fence with `include` takes its content from a file, here a Python program listed with its highlighting.

````md
```python include="hanoi.py"
```
````

```python include="hanoi.py"
```

## Inline

### Emoji

Shortcodes and Unicode emoji are typeset with the emoji font of the `fonts.emoji` setting — OpenMoji black unless told otherwise.

```md
:smile:
:heart:
```

> :smile:
> :heart:

```md
😊 🚀 🍕 🎉 🐍 🌍 💻
📚 🎨 👽 👋 🤖 🦄 🧠
```

> 😊 🚀 🍕 🎉 🐍 🌍 💻
> 📚 🎨 👽 👋 🤖 🦄 🧠

### Keys

`++key+key++` sets keyboard shortcuts as key caps.

```md
++Ctrl+C++
```

> ++Ctrl+C++

### Progress bars

````markdown
[=25% "Research"]
[=50% "Implementation"]
[=75% "Review"]
[=100% "Launch"]{.thin}
````

[=25% "Research"]
[=50% "Implementation"]
[=75% "Review"]
[=100% "Launch"]{.thin}

### Escaping

A backslash makes any punctuation literal, so a `*`, a `_` or a `{` can be written as it is.

```md
\*not emphasis\*, a literal \{brace\} and a \# that is no heading.
```

> \*not emphasis\*, a literal \{brace\} and a \# that is no heading.

## Front matter

A YAML block at the top of the document carries the metadata and the `press` settings: the template, its attributes, the slots, the fonts.

```md
---
title: My document
author: Alice
press:
  template: article
  toc: true
---

# Title
```
