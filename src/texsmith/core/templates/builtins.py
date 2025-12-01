"""Registry helpers for templates built directly into TeXSmith."""

from __future__ import annotations

from importlib import import_module

from .base import WrappableTemplate


_BUILTIN_FACTORIES: dict[str, str] = {
    "article": "texsmith.templates.article:Template",
    "book": "texsmith.templates.book:Template",
    "letter": "texsmith.templates.letter:Template",
    "snippet": "texsmith.templates.snippet:Template",
}

_ALIASES: dict[str, str] = {
    "formal-letter": "letter",
}

_PREFIXES = ("texsmith:", "texsmith.", "texsmith/", "builtin:", "builtin.", "builtin/")


def _normalise_identifier(identifier: str | None) -> str | None:
    if identifier is None:
        return None

    candidate = identifier.strip().lower()
    if not candidate:
        return None

    for prefix in _PREFIXES:
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix) :]
            break

    candidate = candidate.strip("./")
    candidate = candidate.replace("_", "-")
    return candidate or None


def load_builtin_template(identifier: str) -> WrappableTemplate | None:
    """Return a built-in template instance matching ``identifier`` when possible."""
    slug = _normalise_identifier(identifier)
    if slug is None:
        return None

    resolved = _ALIASES.get(slug, slug)
    factory_path = _BUILTIN_FACTORIES.get(resolved)
    if factory_path is None:
        return None

    module_name, _, attr_name = factory_path.partition(":")
    if not module_name:
        return None

    module = import_module(module_name)
    factory = getattr(module, attr_name or "Template")
    template = factory()
    return template


def iter_builtin_templates() -> tuple[str, ...]:
    """Return the available built-in template slugs."""
    return tuple(sorted(_BUILTIN_FACTORIES))


__all__ = ["iter_builtin_templates", "load_builtin_template"]
