# Mermaid Configuration

TeXSmith will automatically pick up a `mermaid-config.json` sitting next to the template's `manifest.toml`. The `assets` pass passes this config to Mermaid for every diagram rendered with that template.

## Using a Built-in Template

The built-in `article` template ships with a `mermaid-config.json`. To inspect or override it:

```bash
texsmith --list-templates                    # every discoverable template and its path
texsmith --template article --template-info  # what this one declares
```

To customize, scaffold the template into your tree, adjust the file, and point `--template` at the copy:

```bash
texsmith --template article --template-scaffold ./templates/article
$EDITOR ./templates/article/template/mermaid-config.json
texsmith doc.md --template ./templates/article
```

## Adding Mermaid Config to a Custom Template

1. Place `mermaid-config.json` next to `manifest.toml`.
2. TeXSmith will expose the path via `template.extras["mermaid_config"]` so the renderer can pass it to Mermaid.
3. No manifest changes are required; the presence of the file is enough.

Typical options include theme, font, backgroundColor, and securityLevel. See https://mermaid.js.org/config/theming.html for full reference.
