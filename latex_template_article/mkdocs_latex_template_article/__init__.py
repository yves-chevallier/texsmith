"""Article template integration for mkdocs-latex."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Mapping

from mkdocs_latex.templates import TemplateError, WrappableTemplate
from mkdocs_latex.utils import escape_latex_chars


_PACKAGE_ROOT = Path(__file__).parent.resolve()


class Template(WrappableTemplate):
    """Expose the article template as a wrappable template instance."""

    _DEFAULT_PAPER_OPTION = "a4paper"
    _DEFAULT_ORIENTATION = "portrait"
    _VALID_PAPER_BASES = {
        "a0",
        "a1",
        "a2",
        "a3",
        "a4",
        "a5",
        "a6",
        "b0",
        "b1",
        "b2",
        "b3",
        "b4",
        "b5",
        "b6",
        "letter",
        "legal",
        "executive",
    }
    _VALID_ORIENTATIONS = {"portrait", "landscape"}

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
        self._apply_metadata(context)

        paper_option = self._normalise_paper_option(context.get("paper"))
        orientation_option = self._normalise_orientation_option(context.get("orientation"))

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

    def _apply_metadata(self, context: dict[str, Any]) -> None:
        raw_meta = context.get("meta")
        if not isinstance(raw_meta, Mapping):
            return

        nested_meta = raw_meta.get("meta") if isinstance(raw_meta.get("meta"), Mapping) else None
        meta_payload: Mapping[str, Any] = nested_meta or raw_meta

        title = self._coerce_string(meta_payload.get("title"))
        if title:
            context["title"] = escape_latex_chars(title)

        subtitle = self._coerce_string(meta_payload.get("subtitle"))
        if subtitle:
            context["subtitle"] = escape_latex_chars(subtitle)

        author_value = self._format_authors(meta_payload.get("authors"))
        if author_value:
            context["author"] = author_value
        else:
            fallback_author = self._coerce_string(meta_payload.get("author"))
            if fallback_author:
                context["author"] = escape_latex_chars(fallback_author)

        date_value = self._coerce_string(meta_payload.get("date"))
        if date_value:
            context["date"] = escape_latex_chars(date_value)

        context.pop("meta", None)
        context.pop("authors", None)

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

    def _normalise_paper_option(self, value: Any) -> str:
        if value is None or value == "":
            return self._DEFAULT_PAPER_OPTION

        if not isinstance(value, str):
            raise TemplateError(
                f"Invalid paper option type '{type(value).__name__}' for article template."
            )

        candidate = value.strip().lower()
        if not candidate:
            return self._DEFAULT_PAPER_OPTION

        if candidate.endswith("paper"):
            candidate = candidate[:-5]

        if candidate not in self._VALID_PAPER_BASES:
            allowed = ", ".join(sorted(f"{base}paper" for base in self._VALID_PAPER_BASES))
            raise TemplateError(
                f"Invalid paper option '{value}' for article template. Allowed values: {allowed}."
            )

        return f"{candidate}paper"

    def _normalise_orientation_option(self, value: Any) -> str:
        if value is None or value == "":
            default = self._DEFAULT_ORIENTATION
        elif not isinstance(value, str):
            raise TemplateError(
                f"Invalid orientation type '{type(value).__name__}' for article template."
            )
        else:
            default = value.strip().lower()

        if not default:
            default = self._DEFAULT_ORIENTATION

        if default not in self._VALID_ORIENTATIONS:
            allowed = ", ".join(sorted(self._VALID_ORIENTATIONS))
            raise TemplateError(
                "Invalid orientation option "
                f"'{value}' for article template. Allowed values: {allowed}."
            )

        return "landscape" if default == "landscape" else ""


__all__ = ["Template"]
