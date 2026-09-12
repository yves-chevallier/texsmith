---
name: writing-texsmith
description: Author Markdown documents for TeXSmith (the TMark → LaTeX/Typst converter). Use whenever writing or editing a .md file meant to be rendered to PDF with `texsmith` — covers YAML front matter, templates & slots, page breaks with `---`, definition lists, figures/tables with captions and cross-references, callouts, math, code, references and citations with `@`, index entries with `#[…]`, and the syntax gotchas that make a build fail.
---

# Writing documents for TeXSmith

TeXSmith converts **TMark** — CommonMark plus the extension set every MkDocs site
loads, plus four syntactic families for what print needs — into **LaTeX** (default) or
**Typst**, then optionally compiles a PDF. This skill is the reference for producing
`.md` sources that render cleanly on the first build.

**Golden rule — separate content from form.** Everything about *appearance* (template,
paper size, fonts, margins, callout style, title, authors) lives in the **YAML front
matter**. The body carries only ideas, prose, and equations. Never hardcode LaTeX
styling in the body unless there is no TMark equivalent.

**Check your work.** `tmark check --strict document.md` parses, resolves and lints the
file: unresolved references, undeclared counter prefixes, malformed tables, deprecated
spellings. `tmark lint --fix document.md` rewrites the deprecated spellings (use
`--diff` or `--stdout` to preview). Run it before handing a document off.

Build command (for reference — you author the `.md`, the user builds):

```bash
texsmith document.md -o build/ --build            # LaTeX → PDF (Tectonic)
texsmith document.md references.bib -t book -o build/ --build
texsmith document.md --format typst -o build/ --build
```

---

## 0. The two sigils and the four families

Everything TMark adds on top of CommonMark is one of four shapes, and two inline
sigils: **`#` defines, `@` refers.**

| Family | Shape | Example |
| ------ | ----- | ------- |
| Attributes | `{…}` *after* the element | `![Trace](t.png){width=60%}` |
| Roles | name *before* the content | `{aside}[see Prandtl 1921]`, `{raw latex}(\clearpage)` |
| Containers | `::: name {attrs}` … `:::` | `::: warning {title="…"}` |
| Data directives | fence info `<lang> <node>` | ```` ```yaml table ````, ```` ```latex raw ```` |

Roles take **brackets** when the payload is content the reader sees and Markdown parses
(`{index}[endianness]`), **parentheses** when it is a verbatim argument the processor
consumes (`{include}(chapter.md)`, `{raw latex}(\newpage)`). Never both.

Attribute lists hold `#id`, `.class` and `key=value`, space-separated, quoted when the
value has spaces. There are no bare-word attributes: write `{collapsed=true}`.
Attributes need a host; for running text, wrap it in a span: `[this claim]{#claim:one}`.

---

## 1. YAML front matter (mandatory scaffolding)

A document opens with a YAML island fenced by `---` at the **very top** of the file
(line 1). Document metadata (`title`, `authors`, `date`, `lang`, `id`) stays at the
**root**, where MkDocs and Pandoc read it; everything TeXSmith owns goes under `press:`.

```md
---
title: Albert Einstein
subtitle: His Life and Achievements
authors:
  - name: Ada Lovelace
    affiliation: Analytical Engine
  - name: Grace Hopper
date: 2025-03-15        # ISO date, or "commit" for last git commit date
lang: en-GB
press:
  template: book        # article (default) | book | letter
  paper: a4             # a4 | a5 | letter …
  base_level: chapter   # part | chapter | section — what the top `#` maps to
  fonts: adventor
  callouts:
    style: fancy        # fancy (default) | classic | minimal
  slots:
    abstract: Abstract    # map a "## Abstract" section into the template's slot
    preface: Preface
  declare:              # kinds: what things *are* (§12)
    counters:
      fw: {name: Finding, format: "FW-{n:02d}"}
  sources:              # where references resolve (§12)
    bibliography:
      einstein1905: https://doi.org/10.1002/andp.19053221004
  features:             # the switch registry
    figures.exec: false
---
```

Key fields:

`template`
:   `article` (default), `book`, or `letter`. Pick `book` for long multi-chapter
    documents, `letter` for correspondence (see §15), `article` otherwise.

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

Any front-matter value is available in the body as `{{ key }}` or `{{ press.template }}`
— substitution only, no logic.

⚠️ **Deprecated:** top-level `bibliography:`, `crossrefs:`, `counters:`, `glossary:`,
`acronyms:`, `admonitions:` and `press.callout_style` are the 0.6 layout. They still
work and warn; `tmark lint --fix` moves them.

---

## 2. Document structure & page breaks

Headings use standard `#`…`######`. Numbering and the mapping to LaTeX sectioning is
driven by `base_level`, so **do not** manually number headings. Two classes act one
heading at a time: `{.unnumbered}` and `{.unlisted}`.

**Page break = a divider.** A line containing only `---` (with a blank line before and
after) is a divider node, which the paged templates render as `\clearpage`. This is the
way to force a page break from Markdown; the web shows `<hr>`.

```md
Last paragraph of the current page.

---

First paragraph of the next page.
```

⚠️ **Gotcha:** because `---` is a page break, never use it as a decorative section
separator. The `---` at the very top of the file is the front-matter fence, not a rule.
To break inline instead, drop `{raw latex}(\clearpage)` into a paragraph.

---

## 3. Text formatting

Each inline node has a role as its canonical spelling and, usually, a familiar
shorthand as sugar. Both produce the same node.

```md
*italic*   **bold**   ***bold italic***   ~~strikethrough~~   `inline code`

{sc}[small capitals]   {mark}[highlight]   {sub}[2]   {sup}[3]   {keys}[ctrl+s]
```

⚠️ **Gotchas:** `__double underscores__` render as **small capitals**, not bold — that
is a deliberate deviation from GFM, and `{sc}[…]` is the spelling to prefer. `_` never
opens emphasis inside a word, so `snake_case_name` stays literal.

A run-in heading that opens a paragraph is `{lead}[Boot sequence.] The device powers…`.
A paragraph starting with a short strong span (< 80 chars) is promoted to one
automatically.

---

## 4. Lists

```md
- Unordered
  - Nested

1. Ordered
2. Next

- [x] Completed task
- [ ] Pending task
```

⚠️ **Gotcha:** nest to the *content column* of the parent (two spaces after `- `, three
after `1. `). Four spaces under a `- ` parent is an indented code block.

---

## 5. Definition lists

A term on its own line, then one or more definitions each introduced by `:` followed by
**at least one space** (align continuation lines under the text). Leave a blank line
between entries.

```md
Apple
:   Pomaceous fruit of plants of the genus Malus in
    the family Rosaceae.

Orange
:   The fruit of an evergreen tree of the genus Citrus.
```

Renders as a LaTeX `description` environment. Great for glossaries of terms, option
references, and parameter documentation.

---

## 6. Callouts (admonitions)

The canonical spelling is a container; folding is an attribute, not a second fence.

```md
::: note {title="Optional title"}
Any Markdown, multiple paragraphs allowed.
:::

::: tip {title="Collapsible" collapsed=true}
Folded on the web; `press.details` decides what print does.
:::
```

Built-in types: `note`, `tip`, `warning`, `important`, `danger`, `info`, `hint`,
`seealso`, `question`, `abstract`; plus `theorem`, `lemma`, `corollary`, `proposition`,
`definition`, `proof`. Rendered as `tcolorbox` blocks; style is set globally via
`press.callouts.style` (`fancy` | `classic` | `minimal`).

The PyMdownX spellings `!!! note "Title"` and `??? note "Title"` stay accepted
indefinitely (MkDocs Material renders them natively) and are one node with the `:::`
form. Use `:::` in new documents, `!!!` when the same file must look right on a
Material site that has not been converted.

A new *kind* of callout is a declaration, not new syntax:

```yaml
press:
  declare:
    admonitions:
      solution: {name: Solution, group: Solutions}
  callouts:
    solution: {icon: "🎓", color: "#123456"}
```

Content tabs are a container too: `::: tabs` holding `::: tab {title=Windows}` blocks
(nest with `::::`). `=== "Windows"` is kept indefinitely for the same reason as `!!!`.

---

## 7. Figures, images & captions

Basic image with optional width (percentage or absolute length):

```md
![Alt text](assets/photo.jpg){width=60%}
```

To make it a **numbered, cross-referenceable figure**, follow it with a **caption
line** — a paragraph of its own, `Kind: text {#id}`, adjacent to the float:

```md
![Short caption for the list of figures](assets/photo.jpg){width=60%}

Figure: This is the full caption shown under the figure. {#fig:my-figure}
```

The kinds are `Figure:`, `Table:` and `Listing:`. Always prefix ids with `fig:`,
`tbl:` or `lst:`.

- The image **alt text** is reused as the short caption in the List of Figures.
- Refer to it with `@`, or with a textual link when the prose should carry the wording:

```md
As shown in @fig:my-figure, the result is clear.
As seen in [this figure](#fig:my-figure), the result is clear.
```

**Never** hardcode "Figure 3" — let numbering resolve it — and avoid the words
"above"/"below" (floats move in print; `tmark lint` flags them).

Subfigures are a container:

```md
::: figure {cols=2}
![Boot](boot.png){#fig:boot}
![Crash](crash.png){#fig:crash}

Figure: Watchdog traces before and after the fix. {#fig:traces}
:::
```

⚠️ **Deprecated:** `/// caption` and `/// figure-caption` with an indented `attrs:`
line. Their id could not contain a colon, so `fig:x` silently degraded.

---

## 8. Tables

### Simple pipe tables

```md
| Option        | Description                     |
| ------------- | ------------------------------- |
| `--build`     | Compile the PDF after rendering |
| `--debug`     | Show full tracebacks            |

Table: Caption for the table. {#tbl:options}
```

The caption line goes **after** the table (a line before it is accepted for Pandoc
compatibility but is not what the printer emits). Refer to it with `@tbl:options`.

Add layout metadata with a `yaml table-config` fence immediately after the table;
canonical order is table, `table-config`, caption line.

````md
| Abbr. | Course        | Load |
| ----- | ------------- | ---- |
| Info1 | Informatique  | 120  |

```yaml table-config
columns:
  - {align: left}
  - {align: justify, width: X}   # X = flexible column that wraps
  - {align: right}
```

Table: Course load. {#tbl:courses}
````

### Rich tables (spans, grouped headers, footers)

Use a `yaml table` fence when you need grouped headers, row/column spans, separators, or
footers. It is validated before rendering, so typos fail locally instead of producing a
broken PDF.

````md
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
  - [Total, ["—", "—", "—", "—"]]
```

Table: Quarterly sales. {#tbl:sales}
````

Rules to remember: `~` is an empty cell **and** the "absorbed by a span" marker (every
slot a span covers must be `~`); the first column is the row-label column; quote cell
values that contain Markdown/YAML punctuation. See the table docs for the full schema.

---

## 9. Math

Uses LaTeX/MathJax syntax. Inline with `$…$` (canonical; `\(…\)` is a compatibility
layer); display with `$$…$$`.

```md
Inline: $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$.

$$
\imath \hbar \frac{\partial}{\partial t} \Psi(\mathbf{r},t) =
\left[ -\frac{\hbar^2}{2m} \nabla^2 + V(\mathbf{r},t) \right] \Psi(\mathbf{r},t)
$$
```

⚠️ **Gotcha:** no space right after the opening `$` or `\(` — `$ x$` breaks the parser.

A numbered equation takes an **anchor after the closing delimiter**, and is referred to
like anything else. Equations have an anchor but never a caption line.

```md
$$
E = mc^2
$$ {#eq:einstein}

As shown in @eq:einstein, energy equals mass times $c^2$.
```

The LaTeX-flavoured form (`\begin{equation}\label{eq:x}…` inside `$$`, referenced with
`$\eqref{eq:x}$`) keeps working as a compatibility layer.

---

## 10. Code blocks

A fenced code block is a data directive whose node word defaults to `code`:

````md
```python title="bubble_sort.py" linenums="1" hl_lines="2-3"
def bubble_sort(items):
    for i in range(len(items)):
        ...
```

Listing: Bubble sort, naive version. {#lst:bubble}
````

Options: `title="…"`, `linenums="1"`, `hl_lines="2-3"`, `include="path"` (read the code
from a file at render time). A `Listing:` caption line makes the block a numbered,
referenceable listing — the same rule as every other float, referred to with
`@lst:bubble`.

Highlighted with Pygments by default (`press.code.engine` also accepts `listings`,
`verbatim`, `minted`). Inline highlighted code is `{code py}[print("hi")]`, or the
PyMdownX sugar `` `#!py print("hi")` ``.

Long inline code overflowing the margin? Let it wrap on identifier separators, and
optionally drop its colouring, with `press.code.inline: {breaks: "_./", plain: true}`.

To splice a whole Markdown file, use the `include` role alone on its line:
`{include}(chapters/boot.md)`. It parses the file as TMark, so nested fences are safe
and relative paths inside it are rebased. `--8<-- "file"` is the deprecated sugar.

---

## 11. Cross-references, citations & links

**One sigil for referring: `@`.** The registry the key belongs to decides what it
renders as.

| Goal | Syntax |
| ---- | ------ |
| External URL | `[text](https://…)` or bare `https://…` |
| Link to another project file | `[text](other.md)` |
| Section number (auto) | `[](other.md)` (empty text) |
| Numbered figure/table/eq/listing/section | `@fig:x`, `@tbl:x`, `@eq:x`, `@lst:x`, `@sec:x` |
| Several at once, or with a locator | `@[fig:boot; fig:crash]`, `@[tbl:stock, column 3]` |
| Start of a sentence | `@Fig:x` (capitalises the label word) |
| Citation, narrative | `@einstein1905` |
| Citation, parenthetical | `@[einstein1905, p. 33]`, `@[-einstein1905]` |
| A DOI cited in place | `@doi:10.1002/andp.19053221004` |
| Glossary term | `@gls:solid` |
| Cross-document | `@fwrev:fw:pas-de-temps` |
| Footnote | `text[^1]` + `[^1]: note text.` |
| Index entry | `#[keyword]` or `{index}[keyword]` |
| Counter item | `#(fw:boot-loop)` defines *and* prints; `@fw:boot-loop` refers |

Brackets follow the sigil and are optional: bare `@key` takes one word, and the
bracketed form is required as soon as the reference contains a space. Trailing sentence
punctuation stays out of the key. `@` never fires inside a word, an e-mail address or a
URL; write `\@` to force a literal one, and `\#` for a literal hash before `[` or `(`.

Footnotes are limited to one line in print — keep them tight.

⚠️ **Deprecated:** `[^key]` and `^[k1,k2]` as *citations*, `[](gls:term)`,
`#{prefix:key}`, `{index:reg}[…]`, `{index}[…]{b}`. Real footnotes (`[^1]` with a
definition) are untouched.

---

## 12. References & glossary in front matter

**Bibliography** — inline entries or DOI shortcuts (a `.bib` file also works):

```yaml
press:
  sources:
    bibliography:
      einstein1905: https://doi.org/10.1002/andp.19053221004
      CD2019:
        type: book
        author: "John Doe"
        title: "Example Book"
        year: "2019"
```

**Glossary and acronyms:**

```yaml
press:
  declare:
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

Acronyms can also be declared in the body, PHP-Markdown-Extra style:

```md
The HTML spec is maintained by the W3C.

*[HTML]: HyperText Markup Language
*[W3C]: World Wide Web Consortium
```

**Custom counters** — findings, requirements, risks:

```yaml
press:
  declare:
    counters:
      fw: {name: Finding, format: "FW-{n:02d}", start: 1, scope: document}
```

---

## 13. Asides and margin notes

```md
Hooke's law {aside}[linear only at small strain] holds below the yield point, but
non-linear effects {aside side=left}[see **Prandtl 1921**] dominate above it.

::: aside
A longer **marginal note** attached to the preceding paragraph.
:::
```

`side=` is `left` | `right` | `outer` | `inner`; the default lives in `press.aside`. An
aside is zero-width in the flow, so the spaces around it collapse. (`{margin}[…]{l}` is
the deprecated 0.6 spelling.)

---

## 14. Escaping to raw LaTeX

Only when TMark has no equivalent. Every escape hatch is spelled with the word `raw`,
is tagged with its backend, and is invisible to the others.

````md
```latex raw
\begin{align}
E &= mc^2 \\
\nabla \cdot \vec{E} &= \frac{\rho}{\varepsilon_0}
\end{align}
```
````

Inline form inside a paragraph: `The section ends here {raw latex}(\clearpage) before
the appendix.` The payload is verbatim — parentheses, never brackets. `typst raw` /
`{raw typst}(…)` and `html raw` / `{raw html}(…)` work the same way.

⚠️ **Deprecated:** `/// latex … ///` and `{latex}[…]`.

Where a whole element belongs to one medium, prefer the `media=` attribute over
mirrored raw blocks: `[web only]{media=web}`, `::: note {media=print}`.

---

## 15. The `letter` template

For correspondence, the whole structure lives in front matter; the body is the letter
text and the first heading is the salutation.

```md
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

- [ ] `tmark check --strict document.md` is clean (or every remaining line is understood).
- [ ] Front matter is at line 1, fenced by `---`, valid YAML, with a `template`;
      TeXSmith keys under `press:`, metadata at the root.
- [ ] Headings are **not** manually numbered; `base_level` matches the template.
- [ ] `---` is used **only** for intentional page breaks (blank line before/after).
- [ ] Bold is `**…**`; small caps is `{sc}[…]` (or `__…__` knowingly).
- [ ] Nested list items are indented to the parent's content column.
- [ ] No space after `$`/`\(` in math; a numbered equation carries `$$ … $$ {#eq:x}`.
- [ ] Figures use `![alt](src){width=…}` followed by a `Figure: … {#fig:…}` line.
- [ ] Cross-references and citations use `@…` — no hardcoded numbers, no
      "above"/"below".
- [ ] Tables needing spans/grouped headers use `yaml table`; span slots are `~`; the
      caption line comes after the table.
- [ ] Every citation key exists in `press.sources.bibliography` or a `.bib` file.
- [ ] Raw LaTeX confined to a ```` ```latex raw ```` fence or `{raw latex}(…)`.
- [ ] No deprecated spelling left: `tmark lint --fix --diff document.md` shows nothing.
