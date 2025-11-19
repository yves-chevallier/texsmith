# Examples

Use these projects to verify your toolchain end-to-end. Each section lists prerequisites, the smoke-test command, and the expected artefacts. When wiring CI, reproduce the same commands (plus `--classic-output` if you prefer deterministic logs).

TeXSmith templates are fully customisable: clone one, tweak the manifest, and redefine every slot to match your own layout. You can introduce bespoke page geometries, add new slot names, and ship extra assets so Markdown sections drop exactly where you need them.

## Prerequisites

- Use the built-in `article` template (`-tarticle`) or point to a custom template.
- Ensure TeX Live/MacTeX/MiKTeX provides the packages required by the template (`texsmith --template article --template-info` lists them).
- For diagrams, install Docker and `minlag/mermaid-cli` or configure an alternative converter.

## Scientific Paper

The `examples/paper` folder converts `cheese.md` + `cheese.bib` into a fully typeset paper with bibliography.

### Smoke test

```bash
cd examples/paper
texsmith render cheese.md cheese.bib \
  --template article \
  --output-dir ../../build/examples/paper \
  --build \
  --classic-output
```

Expected artefacts:

- `build/examples/paper/cheese.tex`
- `build/examples/paper/cheese.pdf`
- `build/examples/paper/output/latexmk.log`

![Cheese Article](cheese.png)

## Markdown Feature Showcase

`examples/markdown/features.md` exercises Markdown extensions and custom front-matter overrides.

Use this example to catch regressions in renderer handlers, typography tweaks, and bibliography overrides.

## Automate the suite

Run `scripts/run_example_smoke_tests.sh` from the repository root to execute all
commands sequentially and collect outputs under `build/examples-smoke/`. Wire
the script into CI to keep diagrams and bibliographies green.
