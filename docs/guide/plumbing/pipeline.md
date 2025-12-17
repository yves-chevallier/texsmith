# How does TeXSmith work?

TeXSmith ingests **Markdown** (`.md`), **HTML** (`.html`), **YAML** (`.yaml`), and **BibTeX** (`.bib`), then runs them through a conversion pipeline to produce LaTeX or a finished PDF.

Templates define the layout and expose slots that get filled with content from your sources. The template also relies on **fragments** which are extra layers for extending the features such as a bibliography, glossary, fonts, page geometry, or other typesetting options.

![Workflow diagram of TeXSmith](../../assets/workflow.drawio)

## Internal pipeline

1. **Collect and classify inputs**
   The CLI and `ConversionService` accept Markdown/HTML documents, optional front-matter YAML, and bibliography files. `split_inputs` peels off `.bib`/`.bibtex`, treats a lone YAML file as the only document when needed, and normalises any provided front matter. When documents share front matter, it is deep-merged into each `Document`, with `press.*` metadata validated up front to avoid surprises later.

2. **Normalise documents to HTML**
   `Document.from_markdown` runs Python-Markdown with the bundled extensions (smallcaps, texlogos, index, Mermaid, raw LaTeX fences, etc.), extracts front matter, and caches the resulting HTML. `Document.from_html` can either keep the whole file or extract a selector (`article.md-content__inner` by default). Heading strategies are decided here (keep, drop, or promote the first heading into `press.title`), numbering defaults are resolved, and slot directives declared in front matter (`press.slot.*`) are seeded into `DocumentSlots`.

3. **Bind the template and attributes**
   `build_binder_context` resolves which template runtime to use (`TemplateBinding`) and which slots exist. Template attributes declared in `manifest.toml` (`TemplateAttributeSpec`) are merged in a strict order: template defaults → fragment defaults → front matter (`press.*` or direct fields) → CLI/session overrides. Attribute ownership is enforced so two fragments or the template cannot claim the same attribute. Before anything renders, mustache placeholders in HTML, front matter, and template overrides are expanded against the merged context so later stages see concrete values.

4. **Split content into slots**
   Slot requests come from CLI `--slot`, front matter, or defaults. `extract_slot_fragments` walks the HTML to find the requested headings/IDs, pulls those sections out, and assigns them to template slots (abstract, mainmatter, appendix, etc.). Base heading levels and offsets are computed per slot so sectioning commands line up with the template’s depth configuration. Any missing selectors produce warnings and the remainder of the document flows into the default slot.

5. **Prime context, fragments, and attributes**
   The binder context prepares runtime defaults: language, code engine/style, callout definitions, diagrams backend, emoji mode, and bibliography map. Active fragments are resolved (from template extras or explicit overrides) and each fragment injects its context defaults plus owned attributes. Fragments are small, declarative building blocks (`fragment.toml` or a Python `BaseFragment`) that emit pieces into specific slots (`package`/`input`/`inline`). Examples: `ts-geometry`, `ts-fonts`, `ts-bibliography`, `ts-index`, glossary, code. A fragment may skip rendering via `should_render` (for example, bibliography and index fragments only activate when citations or index entries exist).

6. **Resolve partials**
   LaTeX output is assembled from Jinja partials (one per Markdown/HTML construct). The precedence is explicit: fragment partials → template overrides (`manifest.toml` `latex.template.override`) → core defaults in `src/texsmith/adapters/latex/partials`. Both templates and fragments can declare `required_partials`; missing providers abort with a `TemplateError`. TeXSmith tracks which provider owns each partial so diagnostics clearly name the culprit.

7. **Render HTML fragments to LaTeX**
   Each slot fragment is rendered through `LaTeXRenderer`, with fallback converters registered when external tools are unavailable. Runtime data (base_level, numbered flag, drop_title, bibliography map, partial providers, language, diagram backend) flows to every handler. The `DocumentState` accumulates headings, citations, index terms, script usage/fallback font summaries, glossaries, snippets, callouts, and asset references so later stages can emit the right packages and backmatter.

8. **Fonts and script matching**
   As text is rendered, the script detector (`texsmith.fonts.scripts`) scans moving arguments (headings, captions, index entries) and wraps non-Latin runs in dedicated LaTeX macros. A cached fallback index built from Noto coverage data chooses per-script font families and emits both font-switching commands and summary stats. The `--fonts-info` flag surfaces the detected scripts, chosen families, and counts after the run.

9. **Bibliography and index resolution**
   Bibliography data comes from `.bib` files plus optional inline front matter entries (including DOI lookups with caching). Only cited keys are written to a generated `texsmith-bibliography.bib`, keeping outputs lean. Citations recorded in `DocumentState` trigger the `ts-bibliography` fragment, which injects package setup and backmatter hooks. Index terms collected by the Markdown extension set `has_index`/`index_terms`, enabling the `ts-index` fragment to load `imakeidx` helpers and drop the `\printindex` block into the `fragment_backmatter` slot.

10. **Template wrap and emission**
    Slot outputs are merged back into the template entrypoint via `wrap_template_document`, alongside template/fragment attributes, required assets, and optional manifest/debug artefacts. When running under `TemplateSession`, the fragments are also materialised as `.tex` files so templates can `\input{}` or `\usepackage{}` them. The resulting `TemplateRenderResult` carries the main `.tex` path, per-fragment outputs, bibliography path (if any), selected template engine, and shell-escape requirement, ready for `texsmith pdf`/Tectonic to produce the final PDF.
