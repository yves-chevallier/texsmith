#set document(
title: "Template Cookbook",
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
#text(size: 1.8em, weight: "bold")[Template Cookbook]]
#v(1.5em)

#ts-callout-style.update("fancy")

This cookbook collects repeatable patterns for building and iterating on TeXSmith templates. Use it in combination with the Templates primer when you need concrete commands or Jinja snippets.

= Clone a starter and rename it

```bash
texsmith --template article --template-scaffold texsmith-template-report
cd texsmith-template-report

# Update package metadata
rg -l "article" | xargs sed -i 's/article/report/g'
```

Adjust `pyproject.toml` (name, version), `template/manifest.toml` (template attributes), and `README.md`. Keep `tests/` so you can run `uv run pytest` after each change.

= Inspect metadata with `–template-info`

```bash
texsmith --template ./texsmith-template-report --template-info
```

Use the output to validate:

- Slots and their depth/offsets.
- Attribute defaults and normalizers (escape rules, `required` flags).
- Declared assets and whether they require templating.
- #ts-logo("TeX") Live year, tlmgr packages, and shell-escape requirements.

== Tip

Run the command inside CI to log tlmgr prerequisites, then cache `tlmgr install ...` between builds.

= Map MkDocs sections to slots

When a template defines slots such as `frontmatter`, `mainmatter`, and `appendix`, wire documents via CLI selectors:

```bash
texsmith docs/intro.md docs/manual.md docs/appendix.md \
  --template texsmith-template-report \
  --slot frontmatter:docs/intro.md \
  --slot mainmatter:docs/manual.md \
  --slot appendix:docs/appendix.md#appendix-a \
  --output-dir build/report \
  --build
```

The `#appendix-a` selector pulls only the section with that ID. Mix selectors freely (IDs, headings, `@document`) to keep Markdown sources modular.

= Restyle a construct

Redefine its contract macro in the template's `.tex`, after
`\VAR{extra_packages}`:

```latex
\VAR{extra_packages}
% Callouts without a frame, inline code without break opportunities.
\tcbset{/ts/callout/.append style={frame hidden, boxrule=0pt}}
\RenewDocumentCommand{\tscodeinline}{O{}m}{\mbox{\texttt{#2}}}
\RenewDocumentCommand{\tsdivider}{}{\bigskip\hrule\bigskip}
```

Guard the redefinition when the fragment is conditional (`ts-code` only loads
when the document has code): `\ifcsname tscodeinline\endcsname … \fi`.

See Contract macros for every macro and its keys, and for the
two heavier levels: restyling through the `pgfkeys` family, and replacing the
fragment outright.

= Keep your own cover and imprint

Do not fork a template to change its front matter. The `book` template reads a
title page and an imprint page from files of yours, and a preamble inline:

```yaml
---
press:
  titlepage: tex/titlepage.tex
  imprint: tex/imprint.tex
  preamble: \usepackage{acmelogo}
---
```

The paths start at the document's directory (at the project directory for a
book built from `mkdocs.yml`), and the files are inlined verbatim, so they can
use `\booktitle`, `\bookauthor`, `\bookdate` and your own `.sty`. See
#link("index.md#a-cover-an-imprint-and-a-preamble-of-your-own")[A cover, an imprint and a preamble of your own].

= Inject custom assets

Add extra files (preamble snippets, latexmk config, fonts) through the `[latex.template.assets]` table:

```toml
[latex.template.assets]
".latexmkrc" = { source = "template/assets/latexmkrc" }
"fonts/MySerif.otf" = { source = "template/assets/fonts/MySerif.otf" }
```

Assets are copied to the render directory. Combine this with `latexmkrc` options (`-shell-escape`) or fontspec helpers to keep users from editing the generated output manually.

= Publish and version responsibly

- Set `compat.texsmith` to a range with an upper bound (`">=0.8,<0.9"`) so an incompatible runtime change fails fast instead of producing a wrong PDF.
- Tag template releases with the same #ts-logo("TeX") Live year used in `manifest.toml`.
- Document tlmgr packages, slot names, and attribute changes in your README so downstream projects can upgrade with confidence.

= Further reading

- Templates primer – attribute schema, manifest format, and slot mechanics.
- API High-Level Workflows – use `ConversionService` to assemble slots programmatically.
- Troubleshooting – debugging latexmk, shell-escape, and bibliography issues once your template ships.
