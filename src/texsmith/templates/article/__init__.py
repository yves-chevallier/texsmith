"""Article template integration for texsmith."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar
import unicodedata

from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.core.templates import TemplateError, WrappableTemplate


_PACKAGE_ROOT = Path(__file__).parent.resolve()


class Template(WrappableTemplate):
    """Expose the article template as a wrappable template instance."""

    _LATIN_RANGE_LIMIT: ClassVar[int] = 0x024F
    _TEXTCOMP_CHARACTERS: ClassVar[set[str]] = {
        "\N{EURO SIGN}",
        "\N{POUND SIGN}",
        "\N{YEN SIGN}",
        "\N{SECTION SIGN}",
        "\N{PILCROW SIGN}",
        "\N{DEGREE SIGN}",
        "\N{PLUS-MINUS SIGN}",
        "\N{MICRO SIGN}",
        "\N{MULTIPLICATION SIGN}",
        "\N{DIVISION SIGN}",
        "\N{COPYRIGHT SIGN}",
        "\N{REGISTERED SIGN}",
        "\N{TRADE MARK SIGN}",
        "\N{VULGAR FRACTION ONE HALF}",
        "\N{VULGAR FRACTION ONE QUARTER}",
        "\N{VULGAR FRACTION THREE QUARTERS}",
        "\N{PER MILLE SIGN}",
    }
    _ALLOWED_PUNCTUATION: ClassVar[set[str]] = {
        "\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}",
        "\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}",
        "\N{SINGLE LEFT-POINTING ANGLE QUOTATION MARK}",
        "\N{SINGLE RIGHT-POINTING ANGLE QUOTATION MARK}",
        "\N{DOUBLE LOW-9 QUOTATION MARK}",
        "\N{LEFT DOUBLE QUOTATION MARK}",
        "\N{RIGHT DOUBLE QUOTATION MARK}",
        "\N{RIGHT SINGLE QUOTATION MARK}",
        "\N{SINGLE LOW-9 QUOTATION MARK}",
        "\N{MIDDLE DOT}",
        "\N{EN DASH}",
        "\N{EM DASH}",
        "\N{HORIZONTAL ELLIPSIS}",
    }

    def __init__(self) -> None:
        try:
            super().__init__(_PACKAGE_ROOT)
        except TemplateError as exc:
            raise TemplateError(f"Failed to initialise article template: {exc}") from exc
        config_path = (self.root / "template" / "mermaid-config.json").resolve()
        self.extras = {"mermaid_config": str(config_path)}

    def prepare_context(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = super().prepare_context(latex_body, overrides=overrides)
        context["ts_extra_disable_hyperref"] = True

        # Transform author metadata into a LaTeX-ready string while preserving defaults.
        raw_authors = context.pop("authors", None)
        author_value = self._format_authors(raw_authors)
        if author_value:
            context["author"] = author_value
        else:
            fallback_author = self._coerce_string(context.get("author"))
            if fallback_author:
                context["author"] = fallback_author
            else:
                context.pop("author", None)

        context.pop("press", None)

        engine_default = self.info.engine or "pdflatex"

        context.setdefault("latex_engine", engine_default)
        context.setdefault("requires_unicode_engine", False)
        context.setdefault("unicode_chars", "")
        context.setdefault("unicode_problematic_chars", "")
        context.setdefault("pdflatex_extra_packages", [])

        candidate_emoji = context.get("emoji")
        if not candidate_emoji:
            fonts_cfg = context.get("fonts")
            if isinstance(fonts_cfg, Mapping):
                candidate_emoji = fonts_cfg.get("emoji")
        if not candidate_emoji:
            press_cfg = context.get("press")
            if isinstance(press_cfg, Mapping):
                press_fonts = press_cfg.get("fonts")
                if isinstance(press_fonts, Mapping):
                    candidate_emoji = press_fonts.get("emoji")

        emoji_mode = self._normalise_emoji_mode(candidate_emoji)
        context["emoji"] = emoji_mode
        if emoji_mode in {"symbola", "color"}:
            context["latex_engine"] = "lualatex"
            context["requires_unicode_engine"] = True

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
            affiliation_value = self._coerce_string(item.get("affiliation"))
            if affiliation_value:
                affiliation_tex = escape_latex_chars(affiliation_value)
                formatted.append(f"{name_tex}\\thanks{{{affiliation_tex}}}")
            else:
                formatted.append(name_tex)

        if not formatted:
            return None
        return " \\and ".join(formatted)

    def _normalise_emoji_mode(self, value: Any) -> str:
        candidate = self._coerce_string(value)
        if candidate:
            candidate_stripped = candidate.strip()
        else:
            default_value = self.info.get_attribute_default("emoji") or "black"
            candidate = self._coerce_string(default_value)
            candidate_stripped = candidate.strip() if candidate else "black"

        if not candidate_stripped:
            return "black"

        lowered = candidate_stripped.lower()
        if lowered in {"artifact", "symbola", "color", "black", "twemoji"}:
            return lowered
        return candidate_stripped

    def wrap_document(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        if context is None:
            prepared = self.prepare_context(latex_body, overrides=overrides)
            context_ref: dict[str, Any] | None = prepared
        else:
            prepared = dict(context)
            context_ref = context if isinstance(context, dict) else None

        preamble_override: str | None = None
        if overrides:
            press_section = overrides.get("press")
            if isinstance(press_section, Mapping):
                override_section = press_section.get("override")
                if isinstance(override_section, Mapping):
                    candidate = override_section.get("preamble")
                    if isinstance(candidate, str) and candidate.strip():
                        preamble_override = candidate.strip()
            if preamble_override is None:
                direct_override = overrides.get("preamble")
                if isinstance(direct_override, str) and direct_override.strip():
                    preamble_override = direct_override.strip()

        if preamble_override:
            existing_extra = prepared.get("extra_packages") or ""
            package_parts = [existing_extra] if existing_extra else []
            package_parts.append(preamble_override)
            prepared["extra_packages"] = "\n".join(part for part in package_parts if part)

        self._analyse_unicode_payload(prepared)

        if context_ref is not prepared and context_ref is not None:
            context_ref.clear()
            context_ref.update(prepared)

        return super().wrap_document(latex_body, overrides=overrides, context=prepared)

    def _analyse_unicode_payload(self, context: dict[str, Any]) -> None:
        unicode_chars = self._collect_unicode_characters(context)
        problematic = []
        extra_packages: set[str] = set()

        base_engine = context.get("latex_engine") or "pdflatex"

        for char in unicode_chars:
            classification = self._classify_character(char)
            if classification == "textcomp":
                extra_packages.add("textcomp")
            elif classification == "unsupported":
                problematic.append(char)

        context["unicode_chars"] = "".join(sorted(unicode_chars, key=ord))
        context["unicode_problematic_chars"] = "".join(sorted(problematic, key=ord))
        context["pdflatex_extra_packages"] = sorted(extra_packages)

        requires_unicode_engine = bool(problematic)
        context["requires_unicode_engine"] = requires_unicode_engine
        context["latex_engine"] = "lualatex" if requires_unicode_engine else base_engine

    def _collect_unicode_characters(self, payload: Any) -> set[str]:
        collected: set[str] = set()
        visited: set[int] = set()

        def _walk(value: Any) -> None:
            if isinstance(value, str):
                for char in value:
                    if ord(char) > 0x7F:
                        collected.add(char)
                return

            if isinstance(value, Mapping):
                identifier = id(value)
                if identifier in visited:
                    return
                visited.add(identifier)
                for key, item in value.items():
                    if isinstance(key, str) and key == "callouts_definitions":
                        continue
                    _walk(item)
                return

            if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
                identifier = id(value)
                if identifier in visited:
                    return
                visited.add(identifier)
                for item in value:
                    _walk(item)

        _walk(payload)
        return collected

    def _classify_character(self, char: str) -> str:
        codepoint = ord(char)
        if codepoint <= self._LATIN_RANGE_LIMIT:
            return "latin"
        if char in self._ALLOWED_PUNCTUATION:
            return "punctuation"
        if char in self._TEXTCOMP_CHARACTERS:
            return "textcomp"

        name: str | None
        try:
            name = unicodedata.name(char)
        except ValueError:
            name = None

        if name and "LATIN" in name:
            return "latin"

        return "unsupported"


__all__ = ["Template"]
