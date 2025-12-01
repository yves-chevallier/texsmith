# Template Cookbook

This cookbook collects repeatable patterns for building and iterating on TeXSmith templates. Use it in combination with the [Templates primer](index.md) when you need concrete commands or Jinja snippets.

## Clone a starter and rename it

```bash
cp -R src/texsmith/templates/article texsmith-template-report
cd texsmith-template-report

# Update package metadata
rg -l "article" | xargs sed -i 's/article/report/g'
```

Adjust `pyproject.toml` (name, version), `template/manifest.toml` (template attributes), and `README.md`. Keep `tests/` so you can run `uv run pytest` after each change.

## Inspect metadata with `template info`

```bash
texsmith --template ./texsmith-template-report --template-info
```

Use the output to validate:

- Slots and their depth/offsets.
- Attribute defaults and normalisers (escape rules, `required` flags).
- Declared assets and whether they require templating.
- TeX Live year, tlmgr packages, and shell-escape requirements.

### Tip

Run the command inside CI to log tlmgr prerequisites, then cache `tlmgr install ...` between builds.

## Map MkDocs sections to slots

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

## Override partials

Place overrides under `overrides/partials/`. Update `manifest.toml`:

```toml
[latex.template]
override = ["partials/bold.tex"]
```

Then create `overrides/partials/bold.tex`:

```tex
\textbf{%
  \BLOCK{ if attrs.emphasis }%
    \VAR{attrs.emphasis}~%
  \BLOCK{ endif }%
  \VAR{text}%
}
```

The renderer will prefer this file over the built-in partial when emitting bold spans.

## Inject custom assets

Add extra files (preamble snippets, latexmk config, fonts) through the `[latex.template.assets]` table:

```toml
[latex.template.assets]
".latexmkrc" = { source = "template/assets/latexmkrc" }
"fonts/MySerif.otf" = { source = "template/assets/fonts/MySerif.otf" }
```

Assets are copied to the render directory. Combine this with `latexmkrc` options (`-shell-escape`) or fontspec helpers to keep users from editing the generated output manually.

## Publish and version responsibly

- Set `compat.texsmith = ">=0.3,<0.4"` so incompatible engine changes fail fast.
- Tag template releases with the same TeX Live year used in `manifest.toml`.
- Document tlmgr packages, slot names, and attribute changes in your README so downstream projects can upgrade with confidence.

## Further reading

- [Templates primer](index.md) – attribute schema, manifest format, and slot mechanics.
- [API High-Level Workflows](../../api/high-level.md) – use `ConversionService` to assemble slots programmatically.
- [Troubleshooting](../troubleshooting.md) – debugging latexmk, shell-escape, and bibliography issues once your template ships.
