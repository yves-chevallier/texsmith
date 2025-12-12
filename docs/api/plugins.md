# Plugin API

Plugins bundle opinionated handler collections so you can enable MkDocs-specific
behaviour (Material tabs, cards, callouts) or ship your own HTML post-processors
without patching the core engine.

`texsmith.plugins` exposes a namespace package populated by the MkDocs hook in
`docs/hooks/mkdocs_hooks.py`. Importing a plugin module registers its handlers
via the standard `@renders` decorator—no extra registry required.

## Loading plugins

```python
# ensure plugin handlers are registered
import texsmith.plugins.material  # noqa: F401

from texsmith import Document, convert_documents

bundle = convert_documents([Document.from_markdown(Path("intro.md"))])
```

When running `texsmith`, use the `--enable-extension` or MkDocs plugin
configuration to import modules before TeXSmith executes. For example, add the
following to your MkDocs `hooks` file:

```python
def on_config(config):
    import texsmith.plugins.material  # registers Material handlers
    return config
```

## Authoring your own plugin

1. Create a module (e.g., `texsmith.plugins.acme`) and import any handlers that
   `@renders` functions depend on.
2. Declare entry points or instruct consumers to `import texsmith.plugins.acme`
   before rendering.
3. Optionally provide a MkDocs plugin/hook so documentation builds load your
   plugin automatically, mirroring what TeXSmith’s docs do with the Material
   helpers.

Keep plugin modules small and focused; most behaviour belongs in dedicated
handler modules under `texsmith.adapters.handlers`.

## Reference

::: texsmith.plugins

::: texsmith.plugins.material
