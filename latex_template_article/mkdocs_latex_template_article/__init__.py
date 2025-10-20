"""Article template integration for mkdocs-latex."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from mkdocs_latex.templates import TemplateError, WrappableTemplate


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
