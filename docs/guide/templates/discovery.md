# Template Discovery

TeXSmith finds templates from multiple locations in a deterministic order:

1. **Built-ins**: shipped with TeXSmith (`article`, `book`, `letter`, `snippet`).
2. **Installed packages**: PyPI distributions named `texsmith-template-*` (or exposing the `texsmith.templates` entry point).
3. **Local tree**: current working directory and any ancestor `templates/` folder. Any `manifest.toml`/`template/manifest.toml` or `__init__.py` counts as a template root.
4. **User directory**: `~/.texsmith/templates/<name>` (same structure as local).

Use the CLI to inspect what was found:

```bash
texsmith --template-info --template article
texsmith templates  # list all visible templates
```

A valid template root contains either `manifest.toml` or `template/manifest.toml`; an `__init__.py` alongside these allows specialised Python logic.

Notes:
- Passing an explicit path (`--template ./templates/custom`) bypasses discovery order.
- Package roots win over same-named local folders; local folders win over the home directory.
- Template manifests can include a `mermaid-config.json` at the root; `--template-info` will surface it.

To scaffold a built-in for customization:

```bash
texsmith templates scaffold article ./templates/article
```

Then point `--template` to that path. Any `mermaid-config.json` placed at the template root will be picked up automatically.
