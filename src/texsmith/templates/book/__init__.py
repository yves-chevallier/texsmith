"""Book template integration for TeXSmith."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from texsmith.core.templates import TemplateError, WrappableTemplate
from texsmith.templates.common import TemplateContextHelpers


_PACKAGE_ROOT = Path(__file__).parent.resolve()


class Template(TemplateContextHelpers, WrappableTemplate):
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



__all__ = ["Template"]
