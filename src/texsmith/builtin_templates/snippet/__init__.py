"""Snippet template integration for TeXSmith."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.templates import TemplateError, WrappableTemplate


_PACKAGE_ROOT = Path(__file__).parent.resolve()


class Template(WrappableTemplate):
    """Expose the snippet template as a wrappable template instance."""

    _CALLOUT_STYLES: ClassVar[set[str]] = {"fancy", "classic", "minimal"}
    _EMOJI_MODES: ClassVar[set[str]] = {"artifact", "symbola", "color"}

    def __init__(self) -> None:
        try:
            super().__init__(_PACKAGE_ROOT)
        except TemplateError as exc:  # pragma: no cover - file system safeguard
            raise TemplateError(f"Failed to initialise snippet template: {exc}") from exc

    def prepare_context(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = super().prepare_context(latex_body, overrides=overrides)

        context["language"] = self._normalise_string(context.get("language"), "english")
        context["width"] = self._normalise_dimension(context.get("width"), "12cm")
        context["margin"] = self._normalise_dimension(context.get("margin"), "6mm")
        context["dogear"] = self._normalise_dimension(context.get("dogear"), "10mm")
        context["border"] = bool(context.get("border", True))
        context["dogear_enabled"] = bool(context.get("dogear_enabled", True))
        context["callout_style"] = self._normalise_callout_style(context.get("callout_style"))
        context["emoji"] = self._normalise_emoji_mode(context.get("emoji"))
        context.setdefault("preamble", "")
        context.setdefault("latex_engine", "lualatex")
        return context

    def _normalise_string(self, value: Any, default: str) -> str:
        if value is None:
            return default
        candidate = str(value).strip()
        return candidate or default

    def _normalise_dimension(self, value: Any, default: str) -> str:
        if value is None:
            return default
        candidate = str(value).strip()
        return candidate or default

    def _normalise_callout_style(self, value: Any) -> str:
        candidate = str(value).strip().lower() if value is not None else ""
        return candidate if candidate in self._CALLOUT_STYLES else "fancy"

    def _normalise_emoji_mode(self, value: Any) -> str:
        candidate = str(value).strip().lower() if value is not None else ""
        return candidate if candidate in self._EMOJI_MODES else "artifact"


__all__ = ["Template"]
