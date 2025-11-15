# `texsmith template info`

Use `texsmith template info` to inspect the metadata declared by a LaTeX template before wiring it into your workflow. The command parses the `manifest.toml`, resolves slots, lists attributes, and dumps the assets that will be copied into the render directory.

```bash
texsmith template info [TEMPLATE]
```

The command is available from two entry points:

- `texsmith template info article` – direct child of the root CLI.
- `texsmith latex template info ./templates/nature` – scoped under the `latex` namespace.

Both invocations produce the same output, so pick whichever best matches your mental model. The root command accepts built-in slugs such as `article` and `letter` in addition to local paths.

## Arguments

| Argument | Description |
| -------- | ----------- |
| `TEMPLATE` | Template name (as installed in the current Python environment) or filesystem path pointing to a template package root. The path can be absolute or relative. |

If you omit the argument, the command prints its contextual help.

## Output

`template info` prints a summary panel showing:

- Template metadata: name, version, Jinja entrypoint, engine, whether `latexmk` needs `--shell-escape`, and tlmgr prerequisites.
- Attribute schema: every manifest attribute along with type information, defaults, and normalisers.
- Declared assets: which files are copied into the render directory, whether they are templated, and which encoding (if any) they use.
- Slots: resolved base levels, offsets, strip-heading behaviour, and the default slot used when no explicit mapping is provided.

When [Rich](https://rich.readthedocs.io/) is available (the default in TeXSmith’s CLI), the command renders tables; otherwise it falls back to plain text.

## Example

```bash
$ texsmith template info article
```

Typical use cases:

- Confirm which slots a template exposes before wiring CLI `--slot` values or front-matter directives.
- List the tlmgr packages required by CI/CD environments prior to running `texsmith render --build`.
- Audit attribute defaults when debugging why a template prints the wrong title, language, or bibliography style.
