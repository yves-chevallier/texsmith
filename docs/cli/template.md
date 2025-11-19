# Template inspection flags

Use the `--template-info` and `--template-scaffold` flags to inspect or copy LaTeX templates before wiring them into your workflow. Both flags piggyback on the main `texsmith` command, so you can reuse the same invocation environment and attribute overrides.

```bash
# Display manifest metadata, slots, attributes, and assets
texsmith --template article --template-info

# Copy a template tree to scaffold-dir/ for customization
texsmith --template ./templates/nature --template-scaffold scaffold-dir/
```

## Arguments

| Argument | Description |
| -------- | ----------- |
| `--template` | Template name (as installed in the current Python environment) or filesystem path pointing to a template package root. The path can be absolute or relative. Required when using either flag. |
| `--template-info` | Prints template metadata and exits. |
| `--template-scaffold DEST` | Copies the selected template into `DEST`, preserving its manifest and assets, then exits. |

If you omit `--template`, TeXSmith falls back to the default `article` template.

## Output

`--template-info` prints a summary panel showing:

- Template metadata: name, version, Jinja entrypoint, engine, whether `latexmk` needs `--shell-escape`, and tlmgr prerequisites.
- Attribute schema: every manifest attribute along with type information, defaults, and normalisers.
- Declared assets: which files are copied into the render directory, whether they are templated, and which encoding (if any) they use.
- Slots: resolved base levels, offsets, strip-heading behaviour, and the default slot used when no explicit mapping is provided.

When [Rich](https://rich.readthedocs.io/) is available (the default in TeXSmith’s CLI), the command renders tables; otherwise it falls back to plain text.

`--template-scaffold` copies the template directory structure to the provided destination. It is ideal for bootstrapping a custom theme or inspecting all assets with your editor.

Typical use cases:

- Confirm which slots a template exposes before wiring CLI `--slot` values or front-matter directives.
- List the tlmgr packages required by CI/CD environments prior to running `texsmith --build`.
- Audit attribute defaults when debugging why a template prints the wrong title, language, or bibliography style.
- Scaffold a built-in template into a local path so you can tweak its manifest, geometry, or assets without editing the originals.
