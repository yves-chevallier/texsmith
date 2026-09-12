#set document(
title: "IR passes and fragment contracts",
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
#text(size: 1.8em, weight: "bold")[IR passes and fragment contracts]]
#v(1.5em)

TeXSmith no longer reads HTML with a bs4 reader and no longer emits #ts-logo("LaTeX") from
Python. The parser, the intermediate representation, the resolver and the
writers are tmark's; what remains on the Python side is the part that needs the
filesystem, the network and a process — and the part that decides what a
construct _looks like_.

```
tmark.parse ─▶ IR ─▶ TeXSmith passes ─▶ tmark.resolve ─▶ tmark.write ─▶ Body { text, map, requires }
```

There are therefore two extension points, and the `@reads` / `@writes`
decorators of 0.6 map onto them:

#table(
columns: 2,
align: (left, left),
table.header([0.6 hook], [0.7 replacement]),
[`@reads` lowering (HTML #ts-script("symbols")[→ ]IR)], [a TMark *container* (`::: name`) plus, when it computes something, an *IR pass*],
[`@writes` emitter (IR #ts-script("symbols")[→ ]#ts-logo("LaTeX"))], [a *contract macro* provided by a fragment, redefined by the template],
[`[latex.template] readers`], [`[latex.template] passes = ["pkg.module:pass"]`],
[`[latex.template] writer`], [redefine the contract macro in the template's `.tex`],
[fragment `partials`, `required_partials`], [the fragment's `provides` list],
)

`readers`, `writer`, `latex.template.override`, fragment `partials` and
`required_partials` are deprecated in 0.7.0 (they warn and are ignored) and
removed in 0.8.0.

= IR passes

A pass is a pure function `(Document, PassContext) -> Document` over the
generated IR models. It never mutates its input, returns the same object when it
has nothing to do, and otherwise rebuilds the tree with `document.evolve(...)`.
Failures never raise: a node is replaced by a visible literal and a diagnostic
is emitted at its span. An exception escaping a pass is a bug.

Two stages surround the one Rust step in the middle:

/ `pre`: before `tmark.resolve`. A `pre` pass may add, remove or rewrite blocks — this
is where includes are spliced, diagrams converted, DOIs fetched, moustaches
expanded.
/ `post`: after `tmark.resolve`. A `post` pass only slices the block list or computes
per-body options, so that the `Resolved` of the whole document stays valid.

```python
from texsmith.core.documents import Document
from texsmith.ir import model
from texsmith.passes import PassContext, spec

@spec("exam-questions", stage="pre", after=("include",))
def run(document: Document, ctx: PassContext) -> Document:
    ir = document.ir
    if ir is None:
        return document
    blocks = tuple(_number(block) for block in ir.blocks)
    if blocks == ir.blocks:
        return document          # nothing to do: hand back the same object
    return document.evolve(ir=ir.model_copy(update={"blocks": blocks}))
```

Order is declared, never implicit: a `PassSpec` names the passes it must run
`after`, and `build_pipeline` performs a stable topological sort that raises
`PassOrderError` on a cycle. Declare a template's passes in its manifest:

```toml
[latex.template]
name = "exam"
version = "1.0.0"
entrypoint = "template/template.tex"
engine = "lualatex"

passes = ["my_exam_pkg.questions:run"]
```

They are resolved with the same import machinery as attribute normalisers and
fragment entrypoints, so a typo fails early with an actionable `TemplateError`,
and they apply *only while the declaring template renders* — exam-style rules
would corrupt unrelated documents, so there is no global entry point.

Keep passes semantic and backend-neutral: a pass rewrites IR nodes and their
attributes, never #ts-logo("LaTeX") strings. The one exception is deliberate and narrow —
the bundled `highlight` pass turns code blocks into `RawBlock{format=latex}`
holding a Pygments payload, because that work is Python-only and reuses the
`latex raw` path rather than making the writer Pygments-aware.

= Custom constructs

The container names TMark knows are a *closed* registry: the callout types
(built-in and declared), `aside`, `figure`, `tabs`, `tab`, `multicolumn` and
`div`. A new _kind_ of thing is a declaration under
`press.declare.admonitions`, not a new container name; a wrapper the template
styles is `::: div` with a class.

```md
::: div {#s1 .sidebar}
Content.
:::
```

On the paged backends every layout container is rendered by one contract,
`\begin{tsdiv}{name}[attrs]` (`#ts-div("name", ..)` in Typst), dispatched on the
name with the attributes forwarded as keys: `#id` becomes `id`, classes become
`class={a,b}`, `key=val` is forwarded as is (`lang` and `media` never are). A
template styles a class through the `pgfkeys` family, or redefines the
environment for a name it knows:

```latex
\tcbset{/ts/div/class/sidebar/.style={grow to left by=2cm}}
\RenewDocumentEnvironment{tsdiv@multicolumn}{O{}}{\begin{multicols}{3}}{\end{multicols}}
```

A container name the registry does not know raises `container-unknown` and
renders its content transparently.

= Contract macros

The writers emit a fixed macro or environment per construct, and a fragment must
define every macro the writer can name. Naming is regular: macros are
`\ts<name>`, environments `ts<name>`, lowercase, one word per construct. At most
one optional keyval group comes first, then the mandatory arguments, content
last.

```latex
\tslead{…}
\tsaside[side=left]{…}
\tsprogress[thin]{0.45}{Launch}
\tskeys{Ctrl,Alt,Del}
\tsindex[registry=physics, main]{sort@formatted!sub}
\begin{tscallout}[kind=warning, title={…}, id=w1, collapsed] … \end{tscallout}
\begin{tscode}[lang=py, title={bubble\_sort.py}, linenums=1, hl_lines={2-3}] … \end{tscode}
\tscodeinline[lang=py]{xs.sort()}
```

Options are `pgfkeys` keyvals under `/ts/<name>/`, and every family ignores
unknown keys, so an older fragment survives a newer writer. Only keys with a
value are serialised; booleans are bare, text is escaped and braced, lists are
braced with commas. Typst mirrors each contract with one hyphenated function
(`#ts-callout`, `#ts-keys`) whose named arguments match the keys.

Which fragment provides which macro is the writer's `Requires.fragments`: a body
that emits `\tscallout` activates `ts-callouts`, one that emits `\tsindex`
activates `ts-index`. Activation is by construction, not by sniffing the
rendered #ts-logo("LaTeX").

= Overriding a construct

Three levels, in increasing order of violence. All of them go in the template's
`.tex`, after `\VAR{extra_packages}` (that is where fragments are
`\usepackage`d).

```latex
\VAR{extra_packages}
% (a) restyle through the pgfkeys family
\tcbset{/ts/code/.append style={frame hidden, boxrule=0pt}}

% (b) redefine the macro, same signature
\RenewDocumentCommand{\tscodeinline}{O{}m}{\texttt{#2}}
\RenewDocumentEnvironment{tsdiv@multicolumn}{O{}}{\begin{multicols}{3}}{\end{multicols}}
```

```yaml
# (c) replace the fragment outright
press:
  fragments:
    disable: [ts-code]
    append: [./my-code.sty]
```

A replacement fragment must define every entry of the fragment's `provides`
list; the check runs at load time against `tmark.fragments()`. See
Contract macros for the full table mapping
each construct to its macro.

= Reference
