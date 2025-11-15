# Handlers

Handlers convert BeautifulSoup nodes into LaTeX fragments. They run inside the
core renderer and are grouped by `RenderPhase` so transformations can hook into
the DOM at the right point.

## Render phases at a glance

| Phase | Purpose | Typical consumers |
| ----- | ------- | ----------------- |
| `RenderPhase.PRE` | Normalise HTML before layout-sensitive transforms (unwrap unwanted tags, capture math spans, detect inline code). | `basic.discard_unwanted`, `inline.inline_code`, diagram preprocessors. |
| `RenderPhase.BLOCK` | Manipulate block-level nodes when structure is stable (convert `<figure>`, extract tabbed content, manage slot boundaries). | `blocks.tabbed_content`, `media.render_mermaid`. |
| `RenderPhase.INLINE` | Render inline formatting once blocks are resolved. | `inline.inline_emphasis`, `links.links`, `inline.abbreviation`. |
| `RenderPhase.POST` | Finalisation pass after children are converted; ideal for numbering, bibliography hooks, or asset emission. | `blocks.tables`, `admonitions.render_admonition`, `media.render_images`. |

Handlers are regular Python callables decorated with `@renders(...)`. The
decorator declares the HTML selectors, phase, and metadata such as priority,
`nestable`, and whether TeXSmith should auto-mark the node as processed.

## Example: add a custom inline macro

```python
from bs4 import Tag

from texsmith.core.context import RenderContext
from texsmith.core.rules import RenderPhase, renders


@renders("span", phase=RenderPhase.INLINE, priority=10, name="callout_chips")
def render_callout_chips(element: Tag, context: RenderContext) -> None:
    if "data-callout" not in element.attrs:
        return
    label = element.get_text(strip=True)
    latex = r"\CalloutChip{%s}" % context.escape(label)
    context.write(latex)
    context.mark_processed(element)
```

Drop the module anywhere on `PYTHONPATH` and import it before calling
`texsmith.render`. For MkDocs sites, add the import inside a `mkdocs` plugin or
`docs/hooks/mkdocs_hooks.py`. For programmatic runs, import the module ahead of
`convert_documents` so the decorator executes at import time.

!!! tip
    Handlers should call `context.mark_processed(element)` when they fully
    consume a node. Leave the node untouched to let lower-priority handlers run.

## Reference

::: texsmith.adapters.handlers

::: texsmith.adapters.handlers._helpers

::: texsmith.adapters.handlers.admonitions

::: texsmith.adapters.handlers.basic

::: texsmith.adapters.handlers.blocks

::: texsmith.adapters.handlers.code

::: texsmith.adapters.handlers.inline

::: texsmith.adapters.handlers.links

::: texsmith.adapters.handlers.media
