# Plugin API

Plugins bundle the build-time helpers an IR pass drives — the snippet
compiler's nested build, the MkDocs site-side HTML rewriting — so you can extend
TeXSmith without patching the core parse → IR → write pipeline.

`texsmith.plugins` exposes a namespace package populated by the MkDocs hook in
`docs/hooks/mkdocs_hooks.py`, re-exporting the maintained plugin modules under
`texsmith.adapters.plugins`.

## Loading plugins

```python
import texsmith.plugins.snippet  # noqa: F401

from texsmith import Document, convert_documents

bundle = convert_documents([Document.from_markdown(Path("intro.md"))])
```

## Authoring your own plugin

1. Create a module (e.g., `texsmith.plugins.acme`) exposing the build-time
   helpers your documents need, and an IR pass that calls them.
2. Declare entry points or instruct consumers to `import texsmith.plugins.acme`
   before rendering.
3. Optionally provide a MkDocs plugin/hook so documentation builds load your
   plugin automatically.

Keep plugin modules small and focused.

## Reference

::: texsmith.plugins

::: texsmith.plugins.snippet
