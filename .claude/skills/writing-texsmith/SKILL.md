---
name: writing-texsmith
description: Author Markdown documents for TeXSmith (the Markdown/HTML → LaTeX/Typst converter). Use whenever writing or editing a .md file meant to be rendered to PDF with `texsmith` — covers YAML front matter, templates & slots, page breaks with `---`, definition lists, figures/tables with captions and cross-references, admonitions, math, code, and the syntax gotchas that make a build fail.
---

# Writing documents for TeXSmith

TeXSmith converts **Markdown** into **LaTeX** (default) or **Typst**, then optionally
compiles a PDF. You author plain Markdown enriched with a few PyMdown extensions and a
handful of TeXSmith-specific conventions. This skill is the reference for producing
`.md` sources that render cleanly on the first build.

**Golden rule — separate content from form.** Everything about *appearance* (template,
paper size, fonts, margins, callout style, title, authors) lives in the **YAML front
matter**. The body carries only ideas, prose, and equations. Never hardcode LaTeX
styling in the body unless there is no Markdown equivalent.

Build command (for reference — you author the `.md`, the user builds):
```bash
texsmith document.md -o build/ --build            # LaTeX → PDF (Tectonic)
texsmith document.md references.bib -t book -o build/ --build
texsmith document.md --format typst -o build/ --build
```

---

## 1. YAML front matter (mandatory scaffolding)

A document opens with a YAML island fenced by `---` at the **very top** of the file
(line 1). Put typographic config under a `press:` block; `title`/`authors`/`date` may
sit either under `press:` or at the root.

```markdown
---
title: Albert Einstein
subtitle: His Life and Achievements
authors:
  - name: Ada Lovelace
    affiliation: Analytical Engine
  - name: Grace Hopper
date: 2025-03-15        # ISO date, or "commit" for last git commit date
press:
  template: book        # article (default) | book | letter
  paper: a4             # a4 | a5 | letter …
  base_level: chapter   # part | chapter | section — what the top `#` maps to
  fonts: adventor
  callout_style: fancy  # fancy (default) | classic | minimal
  slots:
    abstract: Abstract    # map a "## Abstract" section into the template's slot
    preface: Preface
---
```

Key fields:

`template`
:   `article` (default), `book`, or `letter`. Pick `book` for long multi-chapter
    documents, `letter` for correspondence (see §11), `article` otherwise.

`title`
:   If omitted, TeXSmith promotes the document's **first heading** to the title.
    Set `title: null` to render with no title while keeping the first heading as content.

`authors`
:   A string, a list of strings, or a list of `{name, affiliation}` objects. `name` is
    required; a missing name is a hard error.

`date`
:   ISO date (`2024-07-01`), a string, a `{year, month, day}` map, or the special
    `commit` (date of last git commit). Formatted per template locale at render time.

`base_level`
:   What the top-level `#` heading becomes. `chapter` (books), `section` (articles).
    Equivalent to the CLI `--base-level`.

`slots`
:   Map a document section (by heading text) into a named template slot (abstract,
    preface, dedication, colophon…). Inspect a template's slots with
    `texsmith -t <template> --template-info` before wiring them.

Inline **bibliography** and **glossary** also live in front matter — see §9 and §10.

---

## 2. Document structure & page breaks

Headings use standard `#`…`######`. Numbering and the mapping to LaTeX sectioning is
driven by `base_level`, so **do not** manually number headings.

**Page break = a horizontal rule.** A line containing only `---` (with a blank line
before and after) renders as `\clearpage` in LaTeX. This is the *only* way to force a
page break from Markdown.

```markdown
Last paragraph of the current page.

---

First paragraph of the next page.
```

⚠️ **Gotcha:** because `---` is a page break, never use it as a decorative section
separator. The `---` at the very top of the file is the front-matter fence, not a rule.
To break inline instead of using a rule, drop `{latex}[\clearpage]` into a paragraph.

---

## 3. Text formatting

```markdown
*italic*   **bold**   ***bold italic***   ~~strikethrough~~   `inline code`
__small capitals__
```

⚠️ **Gotcha:** `__double underscores__` render as **small capitals**, *not* bold. Use
`**` for bold. A standalone paragraph made of a single short bold span (< 80 chars) is
promoted to a lead-in pseudo-heading (`\tslead`), handy for labelling.

---

## 4. Lists

```markdown
- Unordered
  - Nested
1. Ordered
2. Next

- [x] Completed task
- [ ] Pending task
```

---

## 5. Definition lists

A term on its own line, then one or more definitions each introduced by `:` followed by
**at least one space** (align continuation lines under the text). Leave a blank line
between entries.

```markdown
Apple
:   Pomaceous fruit of plants of the genus Malus in
    the family Rosaceae.

Orange
:   The fruit of an evergreen tree of the genus Citrus.
```

Renders as a LaTeX `description` environment. Great for glossaries of terms, option
references, and parameter documentation.

---

## 6. Admonitions (callouts)

```markdown
!!! note "Optional title"
    Indented body — any Markdown, multiple paragraphs allowed.

??? tip "Collapsible"
    Use `???` for a foldable callout, `???+` for one open by default.
```

Built-in types: `note`, `tip`, `warning`, `important`, `danger`, `info`, `hint`,
`seealso`, `question`, `abstract`. Rendered as `tcolorbox` blocks; style is set globally
via `callout_style` in front matter (`fancy` | `classic` | `minimal`).

---

## 7. Figures, images & captions

Basic image with optional width (percentage or absolute length):

```markdown
![Alt text](assets/photo.jpg){width=60%}
```

To make it a **numbered, cross-referenceable figure**, follow the image with a
`/// caption` block. Attach an id with `attrs: {id: fig:my-figure}` — always prefix
figure ids with `fig:`.

```markdown
![Short caption for the list of figures](assets/photo.jpg){width=60%}

/// caption
    attrs: {id: fig:my-figure}
This is the full caption shown under the figure.
///
```

- The image **alt text** is reused as the short caption in the List of Figures.
- Reference it with the `@[label]` shorthand or an empty-text link to `#fig:…`:

```markdown
As shown in Figure @[fig:my-figure], the result is clear.
As shown in Figure @fig:my-figure, brackets are optional for one-word labels.
As seen in [](#fig:my-figure), the result is clear.
```

Any link whose fragment starts with `fig:` (or `tab:`, `sec:`, `eq:`, `code:`) is
auto-decorated with its number and the locale-correct label word ("Figure"/"figure"/
"Abbildung"…). **Never** hardcode "Figure 3" — let numbering resolve it, and avoid the
words "above"/"below" (floats move in print).

---

## 8. Tables

### Simple pipe tables

```markdown
Table: Caption for the table. {#tbl:stock}

| Option        | Description                     |
| ------------- | ------------------------------- |
| `--build`     | Compile the PDF after rendering |
| `--debug`     | Show full tracebacks            |
```

The `Table: … {#tbl:label}` line directly **before** the table sets its caption and
label. Reference with `Table @[tbl:stock]`.

Add layout metadata to a pipe table with a `yaml table-config` fence immediately after
it (positional column specs — no spans/footers):

````markdown
| Abbr. | Course        | Load |
| ----- | ------------- | ---- |
| Info1 | Informatique  | 120  |

```yaml table-config
columns:
  - {align: left}
  - {align: justify, width: X}   # X = flexible column that wraps
  - {align: right}
```
````

### Rich tables (spans, grouped headers, footers)

Use a `yaml table` fence when you need grouped headers, row/column spans, separators, or
footers. It is validated before rendering, so typos fail locally instead of producing a
broken PDF.

````markdown
Table: Quarterly sales {#tbl:sales}

```yaml table
table:
  width: 100%
columns:
  - Product
  - name: FY24
    columns: [Q1, Q2, Q3, Q4]
    width-group: quarter
rows:
  - [Apples, [120, 135, 150, 140]]
  - separator: {label: Seasonal}
  - [Cherries, {value: "n/a", cols: 4, align: c}]
footer:
  - [Total, [—, —, —, —]]
```
````

Rules to remember: `~` is an empty cell **and** the "absorbed by a span" marker (every
slot a span covers must be `~`); the first column is the row-label column; quote cell
values that contain Markdown/YAML punctuation. See the table docs for the full schema.

---

## 9. Math

Uses LaTeX/MathJax syntax. Inline with `$…$` or `\(…\)`; display with `$$…$$`.

```markdown
Inline: $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$.

$$
\imath \hbar \frac{\partial}{\partial t} \Psi(\mathbf{r},t) =
\left[ -\frac{\hbar^2}{2m} \nabla^2 + V(\mathbf{r},t) \right] \Psi(\mathbf{r},t)
$$
```

⚠️ **Gotcha:** no space right after the opening `$` or `\(` — `$ x$` breaks the parser.

Numbered / referenceable equations use `\label{}` inside an `equation`/`align`
environment (wrapped in `$$`), referenced with `$\eqref{…}$` or the `@[label]` shorthand:

```markdown
$$
\begin{equation} \label{eq:einstein}
E = mc^2
\end{equation}
$$

As shown in Equation @[eq:einstein], energy equals mass times $c^2$.
```

---

## 10. Code blocks

Fenced blocks with a language and optional attributes:

````markdown
```python title="bubble_sort.py" linenums="1" hl_lines="2-3"
def bubble_sort(items):
    for i in range(len(items)):
        ...
```
````

Options: `title="…"`, `linenums="1"`, `hl_lines="2-3"`. Rendered via `minted`.
Inline highlighted code: `` `#!py print("hi")` ``. To make a listing referenceable,
wrap it in a `!!! listing {#code:label}` admonition and reference it with
`Listing @[code:label]`.

---

## 11. Cross-references & links

| Goal                         | Syntax                                  |
| ---------------------------- | --------------------------------------- |
| External URL                 | `[text](https://…)` or bare `https://…` |
| Link to another project file | `[text](other.md)`                      |
| Section number (auto)        | `[](other.md)` (empty text)             |
| Numbered figure/table/eq…    | `@[fig:x]`, `@[tbl:x]`, `@[eq:x]`        |
| Footnote                     | `text[^1]` + `[^1]: note text.`          |
| Index / tag entry            | `topic {index}[keyword]`                 |

Footnotes are limited to one line in print — keep them tight. Citations reuse footnote
syntax with a bibliography key: `Einstein's work.[^einstein1905]` where the key is
defined in front matter or a `.bib` file.

---

## 12. References & glossary in front matter

**Bibliography** — inline entries or DOI shortcuts (a `.bib` file also works):

```yaml
bibliography:
  einstein1905: https://doi.org/10.1002/andp.19053221004
  CD2019:
    type: book
    author: "John Doe"
    title: "Example Book"
    year: "2019"
```

**Glossary** (when the feature is enabled):

```yaml
glossary:
  style: long          # long | short
  groups:
    symbols: Mathematical symbols
  entries:
    "$\\phi$":
      group: symbols
      description: Angle in radians
    AI:
      description: Artificial Intelligence
```

---

## 13. Escaping to raw LaTeX

Only when Markdown has no equivalent. Block form:

```markdown
/// latex
\begin{align}
E &= mc^2 \\
\nabla \cdot \vec{E} &= \frac{\rho}{\varepsilon_0}
\end{align}
///
```

Inline form inside a paragraph: `The section ends here {latex}[\clearpage] before the appendix.`

---

## 14. The `letter` template

For correspondence, the whole structure lives in front matter; the body is the letter
text and the first heading is the salutation.

```markdown
---
press:
  template: letter
  date: 1903-07-14
  signature: signature.svg
  from:
    name: Marie Skłodowska Curie
    address: |
      Laboratory of Physics and Chemistry
      Sorbonne University, Paris
  to:
    name: Leonardo da Vinci
    address: |
      Casa di Leonardo
      Florence
  ps: |
    A postscript line.
---
# Dear Maestro Leonardo

Body of the letter…
```

---

## Pre-flight checklist (avoid failed builds)

Before handing off a TeXSmith document, verify:

- [ ] Front matter is at line 1, fenced by `---`, valid YAML, with a `template`.
- [ ] Headings are **not** manually numbered; `base_level` matches the template.
- [ ] `---` is used **only** for intentional page breaks (blank line before/after).
- [ ] Bold is `**…**`; `__…__` was used only where small caps are actually wanted.
- [ ] No space after `$`/`\(` in math; every `\label` referenced with `@[…]`/`\eqref`.
- [ ] Figures use `![alt](src){width=…}` + `/// caption` with an `id: fig:…`.
- [ ] Cross-references use `@[label]` / empty-text links — no hardcoded numbers or
      "above"/"below".
- [ ] Tables needing spans/grouped headers use `yaml table`; span slots are `~`.
- [ ] Every citation key (`[^key]`) exists in `bibliography` front matter or a `.bib`.
- [ ] Raw LaTeX confined to `/// latex … ///` or `{latex}[…]`.
