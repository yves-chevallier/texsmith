#set document(
title: "Custom Transformers",
)
#set page(
paper: "a4",
margin: 2.5cm,
numbering: none,
footer: context {
if counter(page).final().first() > 1 {
align(center)[#counter(page).get().first()]
}
},
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
#text(size: 1.8em, weight: "bold")[Custom Transformers]]
#v(1.5em)

Transformers convert non-PDF assets (Mermaid, Draw.io, bitmap images) into PDF
fragments before the #ts-logo("LaTeX") renderer emits `\includegraphics`. When the built-in
strategies do not cover your workflow, register custom converters via
`texsmith.adapters.transformers.register_converter`.

= Building a converter

```python
from pathlib import Path

from texsmith.adapters.transformers import register_converter
from texsmith.adapters.transformers.base import CachedConversionStrategy
from texsmith.core.exceptions import TransformerExecutionError

class PlantumlToPdf(CachedConversionStrategy):
    suffix = ".pdf"

    def __init__(self) -> None:
        super().__init__("plantuml")

    def _perform_conversion(self, source: Path | str, *, target: Path, cache_dir: Path, **options):
        jar = Path(options.get("jar", "plantuml.jar"))
        if not jar.exists():
            raise TransformerExecutionError(f"PlantUML jar not found at {jar}")

        command = [
            "java",
            "-jar",
            str(jar),
            "-tpdf",
            "-pipe",
        ]
        # write the PlantUML source to stdin
        import subprocess

        result = subprocess.run(
            command,
            input=Path(source).read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise TransformerExecutionError(result.stderr.strip() or "plantuml failed")

        target.write_bytes(result.stdout.encode("utf-8"))
        return target

register_converter("plantuml", PlantumlToPdf())
```

The base class adds caching, stable file naming, and retry/backoff hooks. Supply
your own `suffix` when the converter emits something other than `.pdf`.

= Wiring the converter

+ Import the module before converting documents (e.g., in `docs/hooks/mkdocs_hooks.py`
or a standalone script).
+ Reference the converter name inside handlers or templates. For example, add a
handler that detects `<pre class="language-plantuml">` blocks and calls
`registry.convert("plantuml", ...)`.
+ Ship optional dependencies (CLI tools, Docker images) alongside the template
README so users know how to enable the converter.

= Handling fallbacks

When TeXSmith cannot find a converter, it installs placeholder strategies that
emit visible warnings and `TODO` boxes in the #ts-logo("LaTeX") output. Use these helpers to
control that behavior:

- `texsmith.adapters.transformers.has_converter("mermaid")` – check whether a
converter is registered before assuming the dependency exists.
- `texsmith.core.conversion.attempt_transformer_fallback` – internal helper
the CLI uses to install placeholder converters when optional dependencies are
missing. Call this only if you need to mimic the CLI’s resilience.

= Further reading

- `texsmith.adapters.transformers.base` – reference for
`CachedConversionStrategy`.
- `texsmith.writers.latex.media` – real-world examples
of how converters integrate with the #ts-logo("LaTeX") writer.
- Template Cookbook – packaging
recommendations so your templates document converter prerequisites.
