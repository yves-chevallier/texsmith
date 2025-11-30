"""Book template integration for TeXSmith."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.core.templates import TemplateError, WrappableTemplate


_PACKAGE_ROOT = Path(__file__).parent.resolve()


class Template(WrappableTemplate):
    """Expose the book template as a wrappable template instance."""

    def __init__(self) -> None:
        try:
            super().__init__(_PACKAGE_ROOT)
        except TemplateError as exc:
            raise TemplateError(f"Failed to initialise book template: {exc}") from exc

    def prepare_context(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = super().prepare_context(latex_body, overrides=overrides)
        context["ts_extra_disable_hyperref"] = True

        raw_authors = context.pop("authors", None)
        author_value = self._format_authors(raw_authors)
        if author_value:
            context["author"] = author_value
        else:
            context.pop("author", None)
        context.pop("press", None)
        return context

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
            affiliation = self._coerce_string(item.get("affiliation"))
            if affiliation:
                affiliation_tex = escape_latex_chars(affiliation)
                formatted.append(f"{name_tex}\\thanks{{{affiliation_tex}}}")
            else:
                formatted.append(name_tex)

        if not formatted:
            return None
        return " \\and ".join(formatted)


__all__ = ["Template"]
