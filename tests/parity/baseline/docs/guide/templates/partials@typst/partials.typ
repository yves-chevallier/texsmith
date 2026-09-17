#set document(
title: "Contract macros",
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
#text(size: 1.8em, weight: "bold")[Contract macros]]
#v(1.5em)

#ts-callout-style.update("fancy")

The #ts-logo("LaTeX") body of a document comes from tmark's writer, which emits a
fixed macro or environment per construct. Structural constructs (emphasis,
lists, headings, figures, tables, links, footnotes) are plain #ts-logo("LaTeX") the
writer owns; the constructs a template may want to restyle are *contract
macros* provided by the `ts-*` fragments. The writer names the fragment in
`Requires.fragments`; the fragment defines the macros; a template restyles a
construct by redefining its macro.

The table of contracts is `tmark.fragments()` (`FRAGMENTS` in
`tmark_ir::registry`); the names follow one convention: macros `\ts<name>`,
environments `ts<name>`, at most one optional keyval group first, content
last. Keys are parsed with `pgfkeys` under `/ts/<name>/` and unknown keys
are ignored, so an older fragment survives a newer writer.

= The macros

#table(
columns: (1fr, 1fr, 1fr, 1fr),
align: (left, left, left, left),
table.header([Fragment], [Macro / environment], [Keys], [Notes]),
[`ts-typesetting`], [`\tslead{…}`], [—], [lead-in of a paragraph (run-in bold line)],
[], [`\tsmark{…}`], [—], [highlight; coloured text on #ts-logo("XeTeX"), `lua-ul` on #ts-logo("LuaTeX"), a colour box otherwise],
[], [`\tsdivider`], [—], [thematic break at the top level of the document; `\clearpage` by default],
[], [`\tsrule[keys]`], [`width`, `thickness`, `above`, `below`], [the same thematic break inside a container (quote, callout, figure, div, list item, cell, aside, note); a full-width rule, never a page break],
[], [`\tsepigraph[source={…}]{…}`], [`source`], [`epigraph`],
[], [`\tsaside[side=left]{…}`], [`side` (`left`, `right`, `inner`, `outer`)], [`marginnote`, with the margin font and width clamp],
[], [`\tsprogress[thin]{0.45}{label}`], [`thin`], [`progressbar`],
[], [`\tsicon{path}`], [—], [`\includegraphics[width=1em]`],
[], [`\tslogo{XeLaTeX}`], [—], [a #ts-logo("TeX") logo word (`typography.tex-logos`) through `hologo`; `\TeX`, `\LaTeX`, `\LaTeXe` are the kernel's],
[], [`\begin{tsdiv}{name}[keys]…\end{tsdiv}`], [`cols`, `title`, `id`, `class`], [dispatches to `tsdiv@<name>`; `multicolumn` and `tab` are defined, any other name is transparent],
[`ts-callouts`], [`\begin{tscallout}[kind=note, title={…}, id=x, class={a,b}, collapsed]…\end{tscallout}`], [`kind`, `title`, `id`, `class`, `collapsed`], [today's `callout` box styles and the `press.callouts.*` colours and icons; an unknown kind is `default`, a missing title is the kind's word],
[`ts-code`], [`\begin{tscode}[lang=py, title={…}, caption={…}, linenums, hl_lines={2-3,7}, id=lst:x, stretch=0.5, engine=pygments]…\end{tscode}`], [`lang`, `title`, `caption`, `linenums`, `hl_lines`, `id`, `stretch`, `engine`, `class`], [verbatim body in every engine; the engine comes from `code.engine` (`pygments`, `minted`, `listings`, `verbatim`)],
[], [`\tscodeinline[lang=py]{…}`], [`lang`], [escaped text, `\texttt`],
[`ts-keystrokes`], [`\tskeys{Ctrl,Alt,Del}`], [—], [one box per key, joined by `+`; a literal comma is braced (`{,}`)],
[`ts-todolist`], [`\begin{tstasklist}\item[\tsdone] … \item[\tstodo] … \item[\tspartial] …\end{tstasklist}`], [—], [`enumitem` list with `amssymb`\/`pifont` markers],
[`ts-glossary`], [`\tsgls{key}`, `\tsacr{key}`], [—], [`\tsgls` is `\gls` (first use expands); `\tsacr` is `\acrshort`, the *short* form wherever it stands],
[`ts-index`], [`\tsindex[registry=r, main]{sort@formatted!sub}`], [`registry`, `main`], [zero-width; `\makeindex[name=r]` per registry of `Requires.index`],
[`ts-bibliography`], [`\parencite`, `\textcite`], [—], [fallbacks onto `\cite` when no `.bib` loads `biblatex`],
[`ts-fonts`], [`\tsscript{slug}{…}`, `\tsemoji{…}`], [—], [the `\text<slug>` fallback font, the emoji font],
[`ts-critic`], [`\tsins{…}`, `\tsdel{…}`, `\tssubst{old}{new}`, `\tscomment{…}`], [—], [critic markup],
[`ts-equations`], [—], [—], [a marker, not a package: the writer names it when an equation carries a label, so the Typst template knows to number equations. Nothing to define on the #ts-logo("LaTeX") side],
)

Identity: for a contract macro the writer passes `id=`; the fragment places
`\phantomsection\label`. Attributes of a container are forwarded as keys
(`#id` #ts-script("symbols")[→ ]`id`, classes #ts-script("symbols")[→ ]`class={a,b}`, `key=val` as is); `lang` and `media`
never are.

The Typst writer emits one hyphenated function per contract (`#ts-callout`,
`#ts-code`, `#ts-keys`, …) with the same argument names, defined in
`src/texsmith/templates/common/texsmith.typ`. That library is inlined ahead of
the body in the generated `.typ`, so the file compiles on its own; a Typst
template redefines a function after it, as a #ts-logo("LaTeX") template redefines a macro
after `\VAR{extra_packages}`.

= Overriding a construct

Three levels, in the template's `.tex` after `\VAR{extra_packages}` (the
fragments are `\usepackage`d there):

+ *Restyle through the pgfkeys family.* `tscallout` and `tscode` are
`tcolorbox` boxes; the family style is appended to their options, and a
class named in `class={…}` applies `/ts/<name>/class/<class>` when it is
defined:
  ```latex
  \tcbset{/ts/code/.append style={frame hidden, boxrule=0pt}}
  \tcbset{/ts/callout/class/wide/.style={grow to left by=2cm}}
  ```
+ *Redefine the macro, same signature.*
  ```latex
  \RenewDocumentCommand{\tscodeinline}{O{}m}{\mbox{\texttt{#2}}}
  \RenewDocumentCommand{\tsdivider}{}{\bigskip\hrule\bigskip}
  \pgfkeys{/ts/rule/.cd, thickness=1pt, width=0.4\linewidth}
  \RenewDocumentEnvironment{tsdiv@multicolumn}{O{}}{\begin{multicols}{3}}{\end{multicols}}
  ```
A custom `::: name` container is a `tsdiv@name` environment defined the
same way (one optional argument, the raw key list; the parsed keys are in
`\ts@div@cols`, `\ts@div@title`, `\ts@div@id`).
+ *Replace the fragment.* `press.fragments: {disable: [ts-code], append:
[./my-code.sty]}`; the replacement must define every `provides` entry of
its row in `tmark.fragments()`.

Guard a redefinition when the fragment is conditional (`ts-code` only loads
when the document has code): `\ifcsname tscodeinline\endcsname … \fi`.

= Former partials

Until 0.6 the #ts-logo("LaTeX") came from Jinja partials under
`src/texsmith/adapters/latex/partials`, overridable per template
(`latex.template.override`) and per fragment (`partials`,
`required_partials`). The partials and all three hooks are gone in 0.8.0: the
writer names a macro and a fragment defines it. The mapping:

#table(
columns: (1fr, 1fr),
align: (left, left),
table.header([Former partial], [Replacement]),
[`italic`, `strong`, `smallcaps`, `subscript`, `superscript`, `strikethrough`, `underline`, `enquote`, `blockquote`], [structural #ts-logo("LaTeX") from the writer],
[`highlight`], [`\tsmark`],
[`lead`], [`\tslead`],
[`horizontal_rule`], [`\tsdivider` (top level), `\tsrule` (in a container)],
[`epigraph`], [`\tsepigraph`],
[`multicolumn`, `tabbed`], [`tsdiv@multicolumn`, `tsdiv@tab`],
[`icon`], [`\tsicon`],
[`counter`, `label`, `ref`, `href`, `url`, `footnote`, `include`], [structural],
[`citation`], [`\cite` (structural); `\parencite`\/`\textcite` fallbacks in `ts-bibliography`],
[`acronym`, `glossary`], [`\tsacr`, `\tsgls`],
[`list_acronyms`, `list_glossary`], [the `ts-glossary` backmatter],
[`index`], [`\tsindex`],
[`keystroke`], [`\tskeys`],
[`choices`], [`tstasklist`],
[`unordered_list`, `ordered_list`, `description_list`, `heading`, `figure`, `figure_tcolorbox`, `table`, `yaml_table`], [structural],
[`pagestyle`], [dropped; the template emits `\thispagestyle` after `\maketitle`],
[`callout`], [`tscallout`],
[`codeblock`, `codeblock_listings`, `codeblock_verbatim`, `codeblock_pygments`], [`tscode`],
[`codeinline`, `codeinlinett`], [`\tscodeinline`],
[`add`, `addition`, `del`, `deletion`, `substitution`, `comment`], [`\tsins`, `\tsdel`, `\tssubst`, `\tscomment`],
[`regex`], [dropped; `\href{…}{\tscodeinline{…}}` by composition],
[`exercises_solutions`], [a template-level partial],
)
