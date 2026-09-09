# TMark for VS Code

Syntax highlighting for **TMark**, the Markdown dialect of
[TeXSmith](https://github.com/yves-chevallier/texsmith). The grammar follows
the recognisers of `specs/tmark.md` (draft 3) and sits on top of VS Code's own
Markdown grammar, so everything Markdown already does keeps working.

## What gets highlighted

| Family | Examples |
| ------ | -------- |
| Attributes | `## Title {#sec:intro .draft lang=en}`, `![Alt](f.png){width=60%}`, `[text]{#claim:one}` |
| Roles | `{aside side=left}[…]`, `{index}[a][b]`, `{raw latex}(\clearpage)`, `{include}(file.md)`, `{code py}[…]` |
| References and citations | `@sec:intro`, `@[fig:a; fig:b]`, `@[see ein05, p. 33]`, `@doi:10.1002/…`, Pandoc's `[@key]` |
| Definitions | `#[term][sub]` index entries, `#(fw:key)` counter items |
| Captions | `Table: … {#tbl:x}`, `Figure: …`, `Listing: …` |
| Containers | `::: figure {cols=2}` … `:::`, PyMdownX `!!! note "Title"`, `??? note`, `/// name` |
| Data directives | ```` ```yaml table ````, ```` ```python image ````, ```` ```latex raw ````, ```` ```grid table ````, fence options (`title=`, `hl_lines=`) |
| Inline sugar | `__small caps__`, `==mark==`, `~sub~`, `^sup^`, `++ctrl+s++`, `[^1]`, `^[inline note]`, critic markup, `{{ moustache }}` |
| Compatibility | `\(…\)`, `\[…\]` math, `--8<--` snippets, `[TOC]`, task items `- [x]` / `- [.]` |

Deprecated spellings (`#{fw:key}`, `{latex}[…]`, `{margin}[…]`, `{index:reg}[…]`,
`/// … ///`, `--8<--`, `::: margin`) are marked `invalid.deprecated.tmark` and
shown struck through by default.

Code spans, fenced blocks, the YAML front matter, math and HTML comments are
left alone: none of the TMark patterns fire there.

## How it applies

* Every `.md` file: the grammar is *injected* into the built-in Markdown
  language, so the preview, links, outline and other Markdown features are
  untouched.
* `.tmark` and `.tmd` files: a dedicated `tmark` language (same grammar).
  Add `"files.associations": {"*.md": "tmark"}` to a workspace to force it.

## Try it

From this directory:

```sh
npm install
npm test                 # tokenise test/sample.md and check the scopes
npm run package          # builds vscode-tmark-<version>.vsix
code --install-extension vscode-tmark-0.1.0.vsix
```

Or open this folder in VS Code and press `F5`: an Extension Development Host
starts with `test/sample.md` open. Use **Developer: Inspect Editor Tokens and
Scopes** to see the scopes under the cursor.

`node test/tokens.mjs some-file.md` prints the tokens and scopes of any file
the way VS Code sees them.

## Scopes

Custom scopes end in `.tmark` and can be recoloured through
`editor.tokenColorCustomizations`. The main ones:

| Scope | Construct |
| ----- | --------- |
| `keyword.other.sigil.define.tmark`, `keyword.other.sigil.refer.tmark` | `#` and `@` |
| `entity.other.attribute-name.id.tmark`, `.class.tmark`, `.attribute.tmark` | `{#id .class key=value}` |
| `entity.name.function.role.tmark`, `variable.parameter.positional.role.tmark` | role head |
| `meta.role.content.tmark`, `string.other.argument.role.tmark` | `[content]`, `(argument)` |
| `support.type.reference.tmark` | reference or citation key |
| `entity.other.attribute-name.index.tmark`, `.counter.tmark`, `support.type.counter-prefix.tmark` | `#[term]`, `#(prefix:key)` |
| `keyword.control.directive.tmark`, `entity.name.type.directive.*.tmark` | `:::`, `!!!`, `???`, and their names |
| `keyword.control.directive.node.tmark` | the node word of a data directive |
| `keyword.other.caption.tmark` | `Table:`, `Figure:`, `Listing:` |
| `markup.smallcaps.tmark`, `markup.highlight.tmark`, `markup.subscript.tmark`, `markup.superscript.tmark`, `markup.keystroke.tmark` | inline sugar |
| `invalid.deprecated.tmark` | deprecated spelling |

## Maintaining the grammar

`syntaxes/*.json` are generated: edit `scripts/build_grammar.py` (the regexes
are Python raw strings, one rule per construct of the spec), then run
`npm run build:grammar` and `npm test`. The tests tokenise `test/sample.md`
with `vscode-textmate` and the Markdown grammar vendored under
`test/grammars/`, which is what VS Code itself uses.
