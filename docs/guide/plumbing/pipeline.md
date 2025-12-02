# Conversion Pipeline Order

TeXSmith’s pipeline is deterministic. When debugging or designing templates/fragments, keep this order in mind:

1. **Markdown → HTML**: Material+pymdown extensions run, then TeXSmith extensions (`texlogos`, `index`, `smallcaps`, Mermaid, etc.). Mustache replacements run over front matter + CLI overrides.
2. **Slot extraction**: front matter `press.slots`/`--slot` selectors split the HTML into slot fragments; heading offsets and title handling are computed here.
3. **Fragment rendering**: fragment attributes resolve (ownership enforced), fragment partials are collected, and fragment pieces render into slot injections or `.sty/.tex` files.
4. **Partial overrides**: fragment partials are applied, then template partial overrides, then core partials. Missing `required_partials` abort with a clear error.
5. **LaTeX rendering**: the HTML fragments render to LaTeX with slot-aware heading levels and bibliography context.
6. **Template wrap**: slots merge into the template entrypoint, template/fragment attributes are injected, assets copy, and optional `latexmkrc`/Tectonic metadata is written.

If a rendering error mentions a missing slot, attribute owner conflict, or partial provider, it occurred at steps 2–4. Use `--debug` to surface richer diagnostics. 
