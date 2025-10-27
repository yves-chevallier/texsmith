"""Modernised LaTeX rendering package."""

from __future__ import annotations

from importlib import import_module
from typing import Any


__all__ = [
    "AssetRegistry",
    "BibliographyCollection",
    "BibliographyIssue",
    "BookConfig",
    "Document",
    "DocumentRenderOptions",
    "DocumentState",
    "DoiBibliographyFetcher",
    "DoiLookupError",
    "HeadingLevel",
    "LaTeXConfig",
    "RenderContext",
    "RenderPhase",
    "RenderSettings",
    "TemplateError",
    "TemplateOptions",
    "TemplateRenderResult",
    "TemplateSession",
    "WrappableTemplate",
    "bibliography_data_from_string",
    "convert_documents",
    "copy_template_assets",
    "get_template",
    "load_template",
    "renders",
    "resolve_heading_level",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "AssetRegistry": ("context", "AssetRegistry"),
    "Document": ("api", "Document"),
    "DocumentRenderOptions": ("api", "DocumentRenderOptions"),
    "HeadingLevel": ("api", "HeadingLevel"),
    "BibliographyCollection": ("bibliography", "BibliographyCollection"),
    "BibliographyIssue": ("bibliography", "BibliographyIssue"),
    "BookConfig": ("config", "BookConfig"),
    "DocumentState": ("context", "DocumentState"),
    "DoiBibliographyFetcher": ("bibliography", "DoiBibliographyFetcher"),
    "DoiLookupError": ("bibliography", "DoiLookupError"),
    "LaTeXConfig": ("config", "LaTeXConfig"),
    "RenderContext": ("context", "RenderContext"),
    "RenderPhase": ("rules", "RenderPhase"),
    "RenderSettings": ("api", "RenderSettings"),
    "TemplateError": ("templates", "TemplateError"),
    "TemplateOptions": ("api", "TemplateOptions"),
    "TemplateRenderResult": ("api", "TemplateRenderResult"),
    "TemplateSession": ("api", "TemplateSession"),
    "WrappableTemplate": ("templates", "WrappableTemplate"),
    "bibliography_data_from_string": ("bibliography", "bibliography_data_from_string"),
    "convert_documents": ("api", "convert_documents"),
    "copy_template_assets": ("templates", "copy_template_assets"),
    "get_template": ("api", "get_template"),
    "load_template": ("templates", "load_template"),
    "resolve_heading_level": ("api", "resolve_heading_level"),
    "renders": ("rules", "renders"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:  # pragma: no cover - fallback for unexpected attribute access
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'") from exc

    module = import_module(f".{module_name}", __name__)
    value = getattr(module, attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:  # pragma: no cover - namespace helpers are tiny
    return sorted(set(globals().keys()) | set(__all__))
