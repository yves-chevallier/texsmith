"""Central registry for TeXSmith's bundled Markdown extensions."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import import_module
from typing import Any


__all__ = [
    "ExtensionSpec",
    "available_extensions",
    "get_extension_spec",
    "load_markdown_extension",
    "load_mkdocs_plugin",
    "register_all_renderers",
]


def _load_attribute(path: str) -> Any:
    module_name, _, attribute = path.partition(":")
    if not module_name or not attribute:
        msg = f"Extension entry point '{path}' must use the 'module:attribute' format."
        raise ValueError(msg)
    module = import_module(module_name)
    target: Any = module
    for chunk in attribute.split("."):
        target = getattr(target, chunk)
    return target


def _normalise_slug(value: str) -> str:
    slug = value.split(":", 1)[0].lower()
    if slug.startswith("texsmith."):
        return slug.removeprefix("texsmith.")
    return slug


@dataclass(frozen=True, slots=True)
class ExtensionSpec:
    """Describe how to import Markdown and renderer hooks for an extension."""

    slug: str
    markdown_entry: str
    renderer_entry: str | None = None
    mkdocs_entry: str | None = None
    description: str | None = None

    @property
    def package_name(self) -> str:
        return f"texsmith.{self.slug}"

    def iter_entry_points(self) -> Iterable[str]:
        """Yield configured entry points for documentation/debugging."""
        yield self.markdown_entry
        if self.renderer_entry:
            yield self.renderer_entry
        if self.mkdocs_entry:
            yield self.mkdocs_entry


_EXTENSIONS: dict[str, ExtensionSpec] = {
    "index": ExtensionSpec(
        slug="index",
        markdown_entry="texsmith.index:TexsmithIndexExtension",
        renderer_entry="texsmith.index:register_renderer",
        mkdocs_entry="texsmith.index:IndexPlugin",
        description="Inline hashtags converted into LaTeX index entries.",
    ),
    "texlogos": ExtensionSpec(
        slug="texlogos",
        markdown_entry="texsmith.texlogos:TexLogosExtension",
        renderer_entry="texsmith.texlogos:register_renderer",
        description="Semantic spans for TeX logos rendered in Markdown and LaTeX.",
    ),
    "smallcaps": ExtensionSpec(
        slug="smallcaps",
        markdown_entry="texsmith.smallcaps:SmallCapsExtension",
        description="Maps '__text__' syntax to small caps spans.",
    ),
    "latex_raw": ExtensionSpec(
        slug="latex_raw",
        markdown_entry="texsmith.latex_raw:LatexRawExtension",
        description="Fence supporting inline raw LaTeX payloads.",
    ),
    "rawlatex": ExtensionSpec(
        slug="rawlatex",
        markdown_entry="texsmith.rawlatex:RawLatexExtension",
        description="Inline {latex}[...] markers and /// latex fences.",
    ),
    "latex_text": ExtensionSpec(
        slug="latex_text",
        markdown_entry="texsmith.latex_text:LatexTextExtension",
        description="Styles the literal 'LaTeX' token with a dedicated span.",
    ),
    "smart_dashes": ExtensionSpec(
        slug="smart_dashes",
        markdown_entry="texsmith.smart_dashes:TexsmithSmartDashesExtension",
        description="Converts '--' and '---' into typographic dashes outside code.",
    ),
    "missing_footnotes": ExtensionSpec(
        slug="missing_footnotes",
        markdown_entry="texsmith.missing_footnotes:MissingFootnotesExtension",
        description="Warns about references to undefined footnotes.",
    ),
    "multi_citations": ExtensionSpec(
        slug="multi_citations",
        markdown_entry="texsmith.multi_citations:MultiCitationExtension",
        description="Normalises '^[a,b]' inline citations before footnotes run.",
    ),
    "mermaid": ExtensionSpec(
        slug="mermaid",
        markdown_entry="texsmith.mermaid:MermaidExtension",
        description="Inlines Mermaid diagrams referenced via Markdown images.",
    ),
    "progressbar": ExtensionSpec(
        slug="progressbar",
        markdown_entry="texsmith.progressbar:ProgressBarExtension",
        renderer_entry="texsmith.progressbar:register_renderer",
        description="Renders `[=50%]` progress blocks via the LaTeX progressbar package.",
    ),
}


def available_extensions() -> list[ExtensionSpec]:
    """Return the registered extension specs sorted by slug."""
    return [_EXTENSIONS[key] for key in sorted(_EXTENSIONS)]


def get_extension_spec(name: str) -> ExtensionSpec:
    """Look up the runtime spec for a given extension slug or qualified name."""
    slug = _normalise_slug(name)
    try:
        return _EXTENSIONS[slug]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"No TeXSmith extension named '{name}'.") from exc


def load_markdown_extension(name: str, **config: Any) -> Any:
    """Instantiate a Python-Markdown extension by slug or qualified name."""
    spec = get_extension_spec(name)
    factory: Callable[..., Any] = _load_attribute(spec.markdown_entry)
    return factory(**config)


def register_all_renderers(renderer: object) -> None:
    """Register every available renderer hook on the provided renderer."""
    for spec in _EXTENSIONS.values():
        if not spec.renderer_entry:
            continue
        register: Callable[[object], None] = _load_attribute(spec.renderer_entry)
        register(renderer)


def load_mkdocs_plugin(name: str) -> type[Any] | None:
    """Return the MkDocs plugin class for an extension, if any."""
    spec = get_extension_spec(name)
    if not spec.mkdocs_entry:
        return None
    plugin_cls: type[Any] = _load_attribute(spec.mkdocs_entry)
    return plugin_cls
