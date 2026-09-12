#set document(
title: "Fragments",
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
#text(size: 1.8em, weight: "bold")[Fragments]]
#v(1.5em)

Fragments are reusable #ts-logo("LaTeX") snippets injected into template slots. Built-in fragments (e.g., geometry, fonts, glossary, index) and custom ones share the same structure:

- `fragment.toml` with `name`, `description`, and either an `entrypoint` or a `files` list.
- Optional `attributes` section describing fragment-owned attributes (ownership enforced).
- A `provides` list naming the contract macros the fragment defines; a fragment that replaces another must provide every entry of its row.
- Optional `should_render` logic (via entrypoint) to render only when needed.

= Manifest shape

```toml
name = "my-fragment"
description = "Short description."

[files.0]
path = "my-fragment.jinja.sty"  # or .tex
slot = "extra_packages"
type = "package"                # package | input | inline
output = "my-fragment"

[attributes.option]
default = true
type = "boolean"
sources = ["press.option", "option"]
description = "Controls feature X."
```

If you prefer Python logic, point `entrypoint` at a callable returning a `BaseFragment` instance.

= Fragment pieces

- `package`: rendered to a `.sty` file and injected via `\usepackage` into the target slot.
- `input`: rendered to `.tex` and injected via `\input{}` into the target slot.
- `inline`: rendered string injected directly into the slot variable (no file emitted).

Slots are validated against the template at render time; inline injections must match declared slots or template variables.

= Attributes

Fragments can declare attributes (ownership enforced) and resolve overrides using the same `TemplateAttributeSpec` model as templates. Attribute defaults are injected into the context before rendering fragment pieces. Attribute ownership matters: if two fragments (or a template) claim the same attribute name, TeXSmith raises a `TemplateError`. Keep each attribute owned by a single fragment or the template to avoid conflicts.

= Contract macros

A fragment defines the macros and environments the writers name, and says so:

```toml
provides = ["tscode", "tscodeinline"]
```

The writer activates a fragment through `Requires.fragments`: a body that emits
`\begin{tscode}` pulls in `ts-code`, one that emits `\tsindex` pulls in
`ts-index`. A macro the writer names, a fragment must define — the check runs at
load time against `tmark.fragments()`, so an incomplete replacement fails early
instead of producing an undefined control sequence.

Replace a bundled fragment outright with `press.fragments`:

```yaml
press:
  fragments:
    disable: [ts-code]
    append: [./my-code.sty]
```

See Contract macros for the table of macros and
their keys.

#ts-callout(kind: "warning", title: [Jinja partials are no longer the rendering layer])[
A fragment's `partials` and `required_partials` keys are deprecated in
0.7.0 — they warn and are ignored — and removed in 0.8.0.]

= Runtime loading

- Built-ins are discovered under `src/texsmith/fragments/**/fragment.toml`.
- Custom fragments can be passed via `press.fragments` in front matter or CLI attributes.
- The registry uses manifest metadata first; entrypoint is a fallback.
- *Entrypoint contract (Python)*: Must expose a module attribute `fragment` that is a `BaseFragment` instance. Legacy `create_fragment()` factories are no longer used.

= Fragment contract (Python)

- Implement a `BaseFragment[Config]` subclass with:
- class attributes: `name`, `description`, `pieces`, `attributes` (TemplateAttributeSpec map), optional `context_defaults`, `provides`, `source`.
- methods: `build_config(context, overrides=None) -> Config`, `inject(config, context, overrides=None) -> None`, `should_render(config) -> bool`.
- Define a `Config` dataclass with `from_context(...)` and `inject_into(context)` methods (plus helpers like `enabled()`).
- Export `fragment = YourFragment()` from `__init__.py`; point `fragment.toml` `entrypoint` to `texsmith.fragments.yourname:fragment`.
- Injection flow: registry merges attribute defaults, builds config, calls `inject`, then checks `should_render` before rendering pieces.

== Minimal example

`src/texsmith/fragments/example/__init__.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.templates.manifest import TemplateAttributeSpec

@dataclass(frozen=True)
class ExampleConfig:
    message: str | None

    @classmethod
    def from_context(cls, ctx: Mapping[str, Any]) -> "ExampleConfig":
        return cls(message=ctx.get("example_message"))

    def inject_into(self, ctx: dict[str, Any]) -> None:
        ctx["ts_example_message"] = self.message or "Hello"

    def enabled(self) -> bool:
        return bool(self.message)

class ExampleFragment(BaseFragment[ExampleConfig]):
    name = "ts-example"
    description = "Tiny example fragment."
    pieces = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-example.jinja.tex"),
            kind="inline",
            slot="extra_packages",
        )
    ]
    attributes = {
        "example_message": TemplateAttributeSpec(
            default=None,
            type="string",
            sources=["press.example.message", "example.message"],
        )
    }
    context_defaults: dict[str, Any] = {"extra_packages": ""}
    config_cls = ExampleConfig
    source = Path(__file__).with_name("ts-example.jinja.tex")

    def build_config(self, context: Mapping[str, Any], overrides=None) -> ExampleConfig:
        return self.config_cls.from_context(context)

    def inject(self, config: ExampleConfig, context: dict[str, Any], overrides=None) -> None:
        config.inject_into(context)

    def should_render(self, config: ExampleConfig) -> bool:
        return config.enabled()

fragment = ExampleFragment()
```

`src/texsmith/fragments/example/fragment.toml`

```toml
name = "ts-example"
description = "Tiny example fragment."
entrypoint = "texsmith.fragments.example:fragment"

[[files]]
path = "ts-example.jinja.tex"
slot = "extra_packages"
type = "inline"
```

= Migration notes for fragment authors

- Prefer `fragment.toml` with `files`, `attributes`, and `provides`; use an entrypoint only when you need Python logic.
- If using Python, return a `BaseFragment` instance via `fragment`; `create_fragment()` and `FragmentDefinition` shims have been removed.
- Declare attribute ownership (implicit `owner = <fragment name>`) to avoid collisions with templates or other fragments.
- Keep slot targets aligned with template variables; inline targets must reference declared slots or template variables, otherwise a `TemplateError` is raised.
