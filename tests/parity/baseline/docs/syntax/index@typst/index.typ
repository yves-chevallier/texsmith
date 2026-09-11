#set document(
  title: "Markdown",
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
  #text(size: 1.8em, weight: "bold")[Markdown]
]
#v(1.5em)

If Markdown is new to you, start with the #link("https://www.markdownguide.org/basic-syntax/")[canonical guide].

The original spec is spartan—tables, diagrams, and other niceties didn’t exist.

Over time new _flavours_ sprouted to fill the gaps. Because TeXSmith initially targeted MkDocs, it aligns with #link("https://python-markdown.github.io/extensions/")[Python-Markdown] (MkDocs’ engine) plus the usual suspects like #link("https://facelessuser.github.io/pymdown-extensions/")[Pymdown Extensions].

For printed documentation, especially for scientific or technical reports, some additional features are required:

- Citations and bibliographies
- Cross-references
- Diagrams (Mermaid, Graphviz, Vega)
- Mathematical formulas (LaTeX math)
- Index
- Glossary and acronyms
- Rich tables (span, multi-line cells, etc.)
- Direct LaTeX injections using fenced `/// latex` blocks or inline `{latex}[...]` snippets that stay hidden in HTML but reach the LaTeX output unchanged

= Markdown is a mess

So many flavours, so many extensions, so many incompatible syntaxes—it’s a jungle. CommonMark tried to herd the cats and mostly succeeded, but fragmentation remains. MyST brought Sphinx-style goodies to Markdown, yet it isn’t MkDocs-compatible, so TeXSmith had to chart its own course.

#link("https://imgs.xkcd.com/comics/standards.png")[#image("standards.svg", width: 60%)]

Source: xkcd#footnote[#link("https://xkcd.com/927/")[xkcd:927]].

TeXSmith is unapologetically opinionated: it curates a stack, sprinkles extra sauce on top, and calls the bundle *Tmark* (TeXSmith Markdown).

= TeXSmith compatibility

== CommonMark

#link("https://commonmark.org/help/")[CommonMark] is the standardized, modern version of Markdown.

#table(
  columns: 3,
  align: (left, left, left),
  table.header([Feature], [Syntax], [Supported]),
  [Italic], [`*x*`], [Yes],
  [Bold], [`**x**`], [Yes],
  [Heading], [`# H`], [Yes],
  [Links], [`[Text](url)`], [Yes],
  [Images], [`![Alt](url)`], [Yes],
  [Inline Code], [`` `code` ``], [Yes],
  [Footnotes], [`[^1]`], [Yes],
  [Tables], [], [Yes],
  [Blockquotes], [`> Quote`], [Yes],
  [Ordered Lists], [`1. Item`], [Yes],
  [Unordered Lists], [`- Item`], [Yes],
  [Horizontal Rules], [`---`], [Yes],
  [Superscript], [`^x^`], [Yes],
  [Subscript], [`~x~`], [Yes],
  [Strikethrough], [`~~x~~`], [Yes],
)

== GitHub Flavored Markdown (GFM)

#link("https://github.github.com/gfm/")[GFM] is the version of Markdown used by GitHub, which extends CommonMark with additional features.

#table(
  columns: 3,
  align: (left, left, left),
  table.header([Feature], [Syntax], [Supported]),
  [Separator], [`***`, `___`], [Yes],
)

== Python Markdown

#link("https://python-markdown.github.io/")[Python-Markdown] is the Markdown engine used by MkDocs. It extends CommonMark with a variety of features through extensions.

#table(
  columns: 4,
  align: (left, left, left, left),
  table.header([Feature], [Syntax], [Extension], [Supported]),
  [Definition Lists], [`: def`], [`def_list`], [Yes],
  [Admonitions], [`!!! note`], [`admonition`], [Yes],
  [Inline Math], [`$\sqrt{x}$`], [`mdx_math`], [Yes],
  [SmartyPants], [`<< >>`, `...`, `--`, `---`], [`smarty`], [Yes],
  [WikiLinks], [`[[Wiki link]]`], [`wikilinks`], [Yes],
)

== PyMdown Extensions

#link("https://facelessuser.github.io/pymdown-extensions/")[Pymdown Extensions] is a popular collection of Markdown extensions for Python-Markdown, which adds many useful features.

#table(
  columns: 4,
  align: (left, left, left, left),
  table.header([Feature], [Syntax], [Extension], [Supported]),
  [Better Emphasis], [`***x***`], [`pymdownx.betterem`], [Yes],
  [Superscript], [`x^2^`], [`pymdownx.caret`], [Yes],
  [Underline], [`^^x^^`], [`pymdownx.caret`], [Yes],
  [Strikethrough], [`~~x~~`], [`pymdownx.tilde`], [Yes],
  [Collapsible Sections], [`??? note`], [`pymdownx.details`], [Yes],
  [Emoji], [`:smile:`], [`pymdownx.emoji`], [Yes],
  [Code Highlight], [`` `#!php echo "Hello";` ``], [`pymdownx.inlinehilite`], [Yes],
  [Keys], [`++ctrl+a++`], [`pymdownx.keys`], [Yes],
  [Magic Links], [`https://acme.com`], [`pymdownx.magiclink`], [Yes],
  [Highlight], [`==x==`], [`pymdownx.mark`], [Yes],
  [Smart Symbols], [`(c)`], [`pymdownx.smartsymbols`], [Yes],
  [Task Lists], [`- [ ]`], [`pymdownx.tasklist`], [Yes],
)

== TeXSmith Extensions

#table(
  columns: 3,
  align: (left, left, left),
  table.header([Feature], [Syntax], [Extension]),
  [Small Caps], [`^^x^^`], [`texsmith.extensions.smallcaps`],
  [Mermaid], [`![](diagram.mmd)`], [`texsmith.extensions.mermaid`],
  [Progress Bars], [`[=75% "Done"]`], [`texsmith.progressbar`],
  [Bibliography], [`[^citekey]`], [`texsmith.bibliography`],
  [Index Entries], [`{index}[entry]` (use `{index:registry}[entry]` to target another registry; add more `[level]` brackets for nesting)], [`texsmith.index`],
  [Acronyms], [`ACME (Acme Corporation)`], [`texsmith.acronyms`],
  [Raw LaTeX], [`/// latex`, `{latex}[x]`], [`texsmith.extensions.latex_raw`],
  [LaTeX Text], [`LaTeX`, `TeXSmith`], [`texsmith.latex`],
)

= Default Extensions

- Python Markdown
- abbr
- admonition
- attr\_list
- def\_list
- footnotes
- smarty
- tables
- mdx\_math
- md\_in\_html
- TeXSmith
- texsmith.extensions.multi\_citations:MultiCitationExtension
- texsmith.extensions.latex\_raw:LatexRawExtension
- texsmith.extensions.missing\_footnotes:MissingFootnotesExtension
- texsmith.extensions.latex\_text:LatexTextExtension
- texsmith.extensions.smallcaps:SmallCapsExtension
- texsmith.extensions.progressbar:ProgressBarExtension
- Pymdown Extensions
- pymdownx.betterem
- pymdownx.blocks.caption
- pymdownx.blocks.html
- pymdownx.caret
- pymdownx.critic
- pymdownx.details
- pymdownx.emoji
- pymdownx.fancylists
- pymdownx.highlight
- pymdownx.inlinehilite
- pymdownx.keys
- pymdownx.magiclink
- pymdownx.mark
- pymdownx.saneheaders
- pymdownx.smartsymbols
- pymdownx.snippets
- pymdownx.superfences
- pymdownx.tabbed
- pymdownx.tasklist
- pymdownx.tilde

= Raw LaTeX Snippets (`/// latex`, `{latex}[...]`)

When you need to insert LaTeX that must not appear in the HTML build, use the dedicated fence:

```md
\newcommand{\R}{\mathbb{R}}
```

For inline tweaks, drop `{latex}[payload]` anywhere inside your paragraph:

```md
Section break {latex}[\clearpage] before the next topic.
```

Both syntaxes create hidden nodes (`<p>` for blocks, `<span>` for inline) so the fragments remain invisible online. During the HTML → LaTeX conversion, TeXSmith spots these nodes and drops the original payload straight into the final document. This makes it safe to declare macros, page tweaks, or any advanced snippet without impacting the web version.
