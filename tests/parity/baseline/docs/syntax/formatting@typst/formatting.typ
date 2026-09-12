#set document(
title: "Text Formatting",
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
#text(size: 1.8em, weight: "bold")[Text Formatting]]
#v(1.5em)

Like vanilla Markdown, you can apply basic text formatting using a variety of
delimiters. Every inline node has a *role* as its canonical spelling, and most
have a familiar shorthand as sugar; both produce the same node.

#table(
columns: 4,
align: (left, left, left, left),
table.header([Node], [Canonical], [Sugar], [LaTeX]),
[Emphasis], [`*x*`], [`_x_`], [`\emph`],
[Strong], [`**x**`], [(none)], [`\textbf`],
[Small caps], [`{sc}[x]`], [`__x__` (X1)], [`\textsc`],
[Strikeout], [`{del}[x]`], [`~~x~~`], [`\sout`],
[Underline], [`{underline}[x]`], [`^^x^^`, only with `inline.insert` on], [`\uline`],
[Highlight], [`{mark}[x]`], [`==x==`], [`\tsmark`],
[Subscript], [`{sub}[x]`], [`~x~` (X3)], [`\textsubscript`],
[Superscript], [`{sup}[x]`], [`^x^`], [`\textsuperscript`],
[Keystroke], [`{keys}[ctrl+s]`], [`++ctrl+s++`], [`\tskeys`],
[Code], [`` `x` ``], [(none)], [engine-dependent],
[Highlighted code], [`{code py}[print(1)]`], [`` `#!py print(1)` ``], [engine-dependent],
)

```md
*(regular)* The quick brown fox jumps over the lazy dog.

*(italic)* *The quick brown fox jumps over the lazy dog.*

*(bold)* **The quick brown fox jumps over the lazy dog.**

*(bold italic)* ***The quick brown fox jumps over the lazy dog.***

*(strikethrough)* ~~The quick brown fox jumps over the lazy dog.~~

*(small capitals)* {sc}[The quick brown fox jumps over the lazy dog.]

*(highlight)* {mark}[The quick brown fox] and *(keys)* {keys}[ctrl+s].
```

`__x__` is small caps, not a second bold: that is deviation X1 of the
#link("index.md#degradation-classes")[degradation classes], disabled by the `strict`
profile. `__` duplicates `**`, and academic writing needs small caps far more
than a second bold — and the difference is visible, not silent.

#figure(
image("snippet-<HASH>.png"),
)

Delimiters stack for bold italic, and `_` never opens emphasis inside a word,
so `snake_case_name` stays literal.

= Lead-in paragraphs (`{lead}[…]`)

A _lead-in_ — a short run-in heading that opens a paragraph — has an explicit
role:

```md
{lead}[Boot sequence.] The device powers the flash before the SoC…
```

A paragraph whose first inline is a strong span shorter than 80 characters is
promoted to a lead-in automatically while the `paragraph.lead` feature is on
(the default; off under `strict`). The promotion is sugar, not magic: it is
named, switchable, and `tmark lint –fix` rewrites it to the role. Either way
TeXSmith emits `\tslead{…}`, defined as:

```latex
\providecommand{\tslead}[1]{\par\noindent\textbf{#1}\par\nobreak\smallskip}
```

This guarantees a no-indent paragraph break and a small vertical breather, so the label looks identical regardless of what precedes it. Without this, `**Méthodologie**` wedged between two tables (`\end{center}` ... `\textbf{…}` ... `\begin{center}`) would render flush left while the same construct after running prose would be indented by `babel-french`'s `\parindent`. With `\tslead`, both cases align.

```md
La synthèse récapitule, pilier par pilier, les forces et faiblesses…

{lead}[Sens critique]

| Python | C |
|--------|---|
| Faible | Fort |

{lead}[Méthodologie]

| Python | C |
|--------|---|
| Correcte | Forte |
```

Written as `**Sens critique**` on a line of its own, the same two labels are
promoted to lead-ins automatically and `tmark lint` says so
(`lead-promotion`). The rule fires when the paragraph opens with a strong span
and nothing else precedes it, and the strong text is shorter than 80
characters. Bold spans inside running prose (`Some **bold** text.`) and bold
paragraphs over the threshold keep their `\textbf{…}` rendering.

Override `\tslead` in a custom preamble snippet to change the visual style — for instance, to add a coloured rule, switch to small caps, or replace the `\smallskip` with `\medskip`:

```latex
\renewcommand{\tslead}[1]{\par\noindent\textsc{#1}\par\nobreak\medskip}
```

#ts-callout(kind: "note")[
In MkDocs, you need to specify how to render small capitals using a custom CSS:

```css
.texsmith-smallcaps {
    font-variant: small-caps;
    letter-spacing: 0.04em;
}
```

Then, include this CSS in your MkDocs configuration under `extra_css`:

```yaml
extra_css:
  - stylesheets/smallcaps.css
```]
