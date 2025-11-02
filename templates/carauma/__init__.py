"""Caraumã book template integration for texsmith."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from texsmith.core.templates import TemplateError, WrappableTemplate
from texsmith.adapters.latex.utils import escape_latex_chars


_PACKAGE_ROOT = Path(__file__).parent.resolve()


class Template(WrappableTemplate):
    """Expose the Caraumã book template."""

    def __init__(self) -> None:
        try:
            super().__init__(_PACKAGE_ROOT)
        except TemplateError as exc:
            raise TemplateError(f"Failed to initialise Caraumã book template: {exc}") from exc

    def prepare_context(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = super().prepare_context(latex_body, overrides=overrides)
        self._apply_metadata(context)
        self._finalise_context(context)
        return context

    def wrap_document(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        if context is None:
            context = self.prepare_context(latex_body, overrides=overrides)
        else:
            context = dict(context)
            self._apply_metadata(context)
            self._finalise_context(context)
        return super().wrap_document(
            latex_body,
            overrides=overrides,
            context=context,
        )

    def _apply_metadata(self, context: dict[str, Any]) -> None:
        raw_press = context.get("press")
        if not isinstance(raw_press, Mapping):
            self._ensure_defaults(context)
            return

        payload = (
            raw_press.get("press") if isinstance(raw_press.get("press"), Mapping) else raw_press
        )

        self._assign_if_missing(context, "title", payload, "title")
        self._assign_if_missing(context, "subtitle", payload, "subtitle")
        self._assign_if_missing(context, "author", payload, "author")
        self._assign_if_missing(context, "translator", payload, "translator")
        self._assign_if_missing(context, "publisher", payload, "publisher")
        self._assign_if_missing(context, "edition_year", payload, "edition_year")
        self._assign_if_missing(context, "edition_statement", payload, "edition_statement")
        self._assign_if_missing(context, "isbn", payload, "isbn")
        self._assign_if_missing(context, "license_text", payload, "license")
        self._assign_if_missing(context, "preface_heading", payload, "preface_heading")
        self._assign_if_missing(context, "preface_dropcap", payload, "preface_dropcap")
        self._assign_if_missing(context, "back_cover_text", payload, "back_cover_text")
        self._assign_if_missing(context, "language", payload, "language")
        self._assign_if_missing(context, "contents_title", payload, "contents_title")
        self._assign_if_missing(context, "copyright_year", payload, "copyright_year")
        self._assign_if_missing(context, "copyright_holder", payload, "copyright_holder")

        if not self._coerce_string(context.get("edition_year")):
            date_candidate = self._coerce_string(payload.get("date"))
            if date_candidate:
                context["edition_year"] = date_candidate[:4]

        if not self._coerce_string(context.get("copyright_year")):
            context["copyright_year"] = self._coerce_string(payload.get("date"))[:4]

        self._ensure_defaults(context)

    def _ensure_defaults(self, context: dict[str, Any]) -> None:
        if not self._coerce_string(context.get("language")):
            default_language = self._coerce_string(self.info.get_attribute_default("language"))
            if default_language:
                context["language"] = default_language
        if not self._coerce_string(context.get("contents_title")):
            default_contents_title = self._coerce_string(
                self.info.get_attribute_default("contents_title")
            )
            if default_contents_title:
                context["contents_title"] = default_contents_title

    def _assign_if_missing(
        self,
        context: dict[str, Any],
        key: str,
        payload: Mapping[str, Any],
        meta_key: str,
    ) -> None:
        current = self._coerce_string(context.get(key))
        if current:
            return
        candidate = self._coerce_string(payload.get(meta_key))
        if candidate:
            context[key] = candidate

    def _finalise_context(self, context: dict[str, Any]) -> None:
        preface_content = context.get("preface")
        preface_text = preface_content if isinstance(preface_content, str) else ""

        if "\\lettrine" in preface_text:
            context.setdefault("preface_dropcap_letter", "")
            context.setdefault("preface_dropcap_tail", "")
            context["preface_body"] = preface_text
        else:
            dropcap_request = self._coerce_string(context.get("preface_dropcap"))
            if dropcap_request:
                letter, tail, _, consumed = self._extract_dropcap(dropcap_request)
                if letter:
                    context["preface_dropcap_letter"] = letter
                    context["preface_dropcap_tail"] = tail
                    context["preface_body"] = self._strip_leading_fragment(
                        preface_text, consumed or dropcap_request
                    )
                else:
                    context["preface_dropcap_letter"] = ""
                    context["preface_dropcap_tail"] = ""
                    context["preface_body"] = preface_text
            else:
                letter, tail, body, _ = self._extract_dropcap(preface_text)
                if letter:
                    context["preface_dropcap_letter"] = letter
                    context["preface_dropcap_tail"] = tail
                    context["preface_body"] = body
                else:
                    context.setdefault("preface_dropcap_letter", "")
                    context.setdefault("preface_dropcap_tail", "")
                    context["preface_body"] = preface_text

        context["edition_line"] = self._build_edition_line(context)
        context["copyright_line"] = self._build_copyright_line(context)
        context["isbn_line"] = self._build_isbn_line(context)

    def _extract_dropcap(
        self,
        text: str,
    ) -> tuple[str | None, str, str, str]:
        if not isinstance(text, str):
            return (None, "", "", "")
        if not text:
            return (None, "", "", "")

        length = len(text)
        whitespace_end = 0
        while whitespace_end < length and text[whitespace_end].isspace():
            whitespace_end += 1
        prefix = text[:whitespace_end]

        index = whitespace_end
        punctuation = ""
        while index < length and not text[index].isalpha():
            punctuation += text[index]
            index += 1
        if index >= length:
            return (None, "", text, "")

        letter = text[index]
        index += 1
        word_end = index
        while word_end < length and text[word_end].isalpha():
            word_end += 1
        tail = text[index:word_end]
        remainder = text[word_end:]
        body = f"{prefix}{punctuation}{remainder}"
        consumed = text[:word_end]
        return (letter, tail, body, consumed)

    def _strip_leading_fragment(self, text: str, fragment: str) -> str:
        if not isinstance(text, str) or not text:
            return ""
        if not isinstance(fragment, str) or not fragment:
            return text

        stripped_text = text.lstrip()
        leading_ws_len = len(text) - len(stripped_text)
        leading_ws = text[:leading_ws_len]
        candidate = fragment.strip()
        if stripped_text.startswith(candidate):
            return leading_ws + stripped_text[len(candidate) :]
        return text

    def _build_edition_line(self, context: Mapping[str, Any]) -> str:
        statement = self._coerce_string(context.get("edition_statement"))
        year = self._coerce_string(context.get("edition_year"))
        parts = [part for part in (statement, year) if part]
        if not parts:
            return ""
        return escape_latex_chars(", ".join(parts))

    def _build_copyright_line(self, context: Mapping[str, Any]) -> str:
        year = self._coerce_string(context.get("copyright_year"))
        holder = self._coerce_string(context.get("copyright_holder"))
        if not holder:
            holder = self._coerce_string(context.get("author"))
        pieces = ["Copyright \\copyright{}"]
        if year:
            pieces.append(escape_latex_chars(year))
        if holder:
            pieces.append(escape_latex_chars(holder))
        if len(pieces) == 1:
            return ""
        return " ".join(pieces)

    def _build_isbn_line(self, context: Mapping[str, Any]) -> str:
        isbn = self._coerce_string(context.get("isbn"))
        if not isbn:
            return ""
        return f"ISBN {escape_latex_chars(isbn)}"

    def _coerce_string(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, Mapping):
            for key in ("text", "name", "value"):
                if key in value:
                    candidate = self._coerce_string(value[key])
                    if candidate:
                        return candidate
            return ""
        if isinstance(value, (list, tuple, set)):
            parts = [self._coerce_string(item) for item in value]
            joined = ", ".join(part for part in parts if part)
            return joined
        return str(value).strip()


__all__ = ["Template"]
