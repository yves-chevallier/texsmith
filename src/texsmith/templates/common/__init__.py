"""Shared helpers and LaTeX assets reused by built-in templates."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from texsmith.adapters.latex.utils import escape_latex_chars


class TemplateContextHelpers:
    """Context-coercion helpers shared by the built-in templates.

    Mixed into the concrete ``Template`` classes (article/book/letter) so the
    string/author normalisation lives in one place rather than being copied per
    template.
    """

    def _coerce_string(self, value: Any) -> str | None:
        if value is None:
            return None
        candidate = value.strip() if isinstance(value, str) else str(value).strip()
        return candidate or None

    def _format_authors(self, payload: Any) -> str | None:
        if not payload:
            return None
        if not isinstance(payload, Iterable) or isinstance(payload, (str, bytes)):
            return None

        formatted: list[str] = []
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            name_value = self._coerce_string(item.get("name"))
            if not name_value:
                continue
            name_tex = escape_latex_chars(name_value)
            affiliation_value = self._coerce_string(item.get("affiliation"))
            if affiliation_value:
                affiliation_tex = escape_latex_chars(affiliation_value)
                formatted.append(f"{name_tex}\\thanks{{{affiliation_tex}}}")
            else:
                formatted.append(name_tex)

        if not formatted:
            return None
        return " \\and ".join(formatted)


__all__ = ["TemplateContextHelpers"]
