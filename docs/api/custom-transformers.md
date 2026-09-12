# Custom Transformers

Transformers convert non-PDF assets (Mermaid, Draw.io, bitmap images) into files
LaTeX can include. They are driven by the [`assets` pass](handlers.md#ir-passes),
which rewrites each image node to point at the converted file before
`tmark.write` emits the figure. When the built-in strategies do not cover your
workflow, register custom converters via
`texsmith.adapters.transformers.register_converter`.

## Building a converter

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

## Wiring the converter

1. Import the module before converting documents (e.g., in `docs/hooks/mkdocs_hooks.py`
   or a standalone script).
2. Reach it from an [IR pass](handlers.md#ir-passes): register a `pre` pass that
   walks the tree for the nodes it owns — a `CodeBlock` with `lang="plantuml"`,
   say — and calls `registry.convert("plantuml", …)`, replacing the node with an
   `Image` that points at the result. Declare it on your template
   (`[latex.template] passes = […]`) so it applies only while that template
   renders.
3. Ship optional dependencies (CLI tools, Docker images) alongside the template
   README so users know how to enable the converter.

## Handling fallbacks

When TeXSmith cannot find a converter, the `assets` pass leaves a visible
literal in the output and emits a diagnostic at the node's span rather than
failing the render — a pass never raises. Use
`texsmith.adapters.transformers.has_converter("mermaid")` to check whether a
converter is registered before assuming the dependency exists, and
`--diagrams-backend playwright|local|docker` to pin which backend is tried
instead of letting the automatic fallback pick.

## Further reading

- [`texsmith.adapters.transformers.base`](transformers.md) – reference for
  `CachedConversionStrategy`.
- [IR passes & fragment contracts](../api/handlers.md) – how the `assets`
  pass drives the converters registered here.
- [Template Cookbook](../guide/templates/template-cookbook.md) – packaging
  recommendations so your templates document converter prerequisites.
