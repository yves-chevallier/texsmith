"""Article template integration for texsmith."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from texsmith.core.templates import TemplateError, WrappableTemplate
from texsmith.adapters.latex.utils import escape_latex_chars


_PACKAGE_ROOT = Path(__file__).parent.resolve()


class Template(WrappableTemplate):
    """Expose the article template as a wrappable template instance."""

    _DEFAULT_PAPER_OPTION = "a4paper"
    _DEFAULT_ORIENTATION = "portrait"
    def __init__(self) -> None:
        try:
            super().__init__(_PACKAGE_ROOT)
        except TemplateError as exc:
            raise TemplateError(f"Failed to initialise article template: {exc}") from exc

    def prepare_context(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = super().prepare_context(latex_body, overrides=overrides)

        # Transform author metadata into a LaTeX-ready string while preserving defaults.
        raw_authors = context.pop("authors", None)
        author_value = self._format_authors(raw_authors)
        if author_value:
            context["author"] = author_value
        else:
            fallback_author = context.get("author") or self.info.get_attribute_default("author")
            if isinstance(fallback_author, str):
                candidate = fallback_author.strip()
                context["author"] = candidate or self.info.get_attribute_default("author")

        context.pop("press", None)

        paper_option = (
            context.get("paper")
            or self.info.get_attribute_default("paper")
            or self._DEFAULT_PAPER_OPTION
        )
        orientation_value = (
            context.get("orientation")
            or self.info.get_attribute_default("orientation")
            or self._DEFAULT_ORIENTATION
        )
        orientation_option = "landscape" if orientation_value == "landscape" else ""

        options = [option for option in (paper_option, orientation_option) if option]
        geometry_options = ["margin=2.5cm"]
        if paper_option:
            geometry_options.append(paper_option)
        if orientation_option:
            geometry_options.append(orientation_option)

        context["paper_option"] = paper_option
        context["orientation_option"] = orientation_option
        context["documentclass_options"] = f"[{','.join(options)}]" if options else ""
        context["geometry_options"] = ",".join(geometry_options)

        return context

    def _coerce_string(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            candidate = value.strip()
        else:
            candidate = str(value).strip()
        return candidate or None

    def _format_authors(self, payload: Any) -> str | None:
        if payload is None:
            return None

        if isinstance(payload, str):
            author = payload.strip()
            return escape_latex_chars(author) if author else None

        candidates: list[Any]
        if isinstance(payload, Mapping):
            candidates = [payload]
        elif isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            candidates = list(payload)
        else:
            return None

        formatted: list[str] = []
        for item in candidates:
            if isinstance(item, str):
                author_name = item.strip()
                if author_name:
                    formatted.append(escape_latex_chars(author_name))
                continue

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


__all__ = ["Template"]
