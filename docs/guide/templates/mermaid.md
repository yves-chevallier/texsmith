# Mermaid Configuration per Template

TeXSmith will automatically pick up a `mermaid-config.json` located at the root of a template (next to `manifest.toml`). The diagrams module passes this config to Mermaid for all diagrams rendered with that template.

## Using a Built-in Template

The built-in `article` template ships with a `mermaid-config.json`. To inspect or override it:

```bash
texsmith --template-info --template article
texsmith templates  # list all discoverable templates
```

To customise, copy the file, adjust options, and point to your modified template directory:

```bash
cp -r $(python - <<'PY'\nfrom texsmith.core.templates import load_template\nfrom pathlib import Path\nt = load_template('article')\nprint(t.root)\nPY) ./templates/article\n# edit ./templates/article/mermaid-config.json\ntexsmith doc.md --template ./templates/article
```

## Adding Mermaid Config to a Custom Template

1. Place `mermaid-config.json` at the template root (same level as `manifest.toml`).
2. TeXSmith will expose the path via `template.extras["mermaid_config"]` so the renderer can pass it to Mermaid.
3. No manifest changes are required; the presence of the file is enough.

Typical options include theme, font, backgroundColor, and securityLevel. See https://mermaid.js.org/config/theming.html for full reference.
