---
title: Firmware Review
date: commit
press:
  template: article
  declare:
    counters:
      fw: {name: Finding, format: "FW-{n:02d}"}
---

## Boot sequence {#sec:boot .draft lang=en}

The device powers the flash before the SoC, see @sec:boot and @[fig:boot; fig:crash].
Time is relative @ein05, and recent work agrees @[see ein05, pp. 33-35; -AI2027, ch. 1].
Cite in place @doi:10.1002/andp.19053221004 or @https://doi.org/10.1002/andp.19053221004.
Pandoc import [@ein05, p. 33] and an escaped \@handle or \#tag; mail me at me@example.com.

{lead}[Boot sequence.] Hooke's law {aside}[linear only at small strain] holds,
but {aside side=left}[see **Prandtl 1921**] dominates {index}[endianness] and
{index main=true registry=physics}[byte order][endianness] {raw latex}(\clearpage).
Inline {code py}[print(1)] and `#!py print(1)`; deprecated {latex}[\textbf{x}], {margin}[note]{l},
{index:physics}[relativity]. Values {{ title }} and {{ press.template }}.

#[endianness] #[byte order][endianness] #(fw:boot-loop) The firmware reboots. Old #{fw:boot-loop}.
An anchor on [this claim]{#claim:one}, a language [this taylor]{lang=en}, [web only]{media=web}.
{include}(chapters/boot.md)

Small caps __x__, highlight ==x==, strike ~~x~~, sub H~2~O, sup E=mc^2^, keys ++ctrl+alt+s++,
insert ^^new^^, footnote[^1], inline note ^[an inline note], progress [=75% "Review"].
{>>a critic comment<<} {++added++} {--removed--} {~~old~>new~~} {==marked==}
Math $a^2$ and \(b^2\) and $$c^2$$ {#eq:inline}.

- [ ] open task
- [x] done task with **bold** and @ref
- [.] partial task
- plain item with @ref and {sc}[caps]

Term
:   Definition, indented continuation lines aligned.

[^1]: The footnote text with @ein05.
*[HTML]: HyperText Markup Language

Table: Fruit stock by warehouse. {#tbl:stock}

| Id | Requirement |
| --- | --- |
| #(n:joy) | Everyone shall be happy @sec:boot |

![Trace](trace.png){width=60% #fig:trace}

Figure: Full caption, with **Markdown**. {#fig:plot}

::: figure {cols=2}
![Boot](boot.png){#fig:boot}
:::

::: warning {title="LaTeX toolchain"}
Install TeX Live before `texsmith --build`, see @sec:boot.
:::

::: margin
Deprecated container.
:::

!!! warning "LaTeX toolchain"
    Install TeX Live, see @sec:boot and {aside}[x].

    A second paragraph.

??? note inline end "Folded"
    Body with #[term].

/// caption
Old caption block.
///

```yaml table
columns: [A, B]
rows: [[1, 2]]
```

```python image include="plot.py"
import matplotlib.pyplot as plt
plt.plot([1, 2, 4, 8])
```

```python title="bubble_sort.py" linenums="1" hl_lines="2-3"
def bubble_sort(items): ...
```

```grid table
+-----+-----+
|  1  |  2  |
+-----+-----+
```

```latex raw
\clearpage % not @ref nor {role}[x]
```

```python
plain = "@ref and #[term] must stay plain"
```

$$
a^2 + b^2 = c^2
$$ {#eq:pythagoras}

\[
x^2 + y^2
\]

--8<-- "snippets/file.md"

[TOC]

Listing: Bubble sort. {#lst:bubble}

<!-- a comment with @ref and {role}[x] -->
