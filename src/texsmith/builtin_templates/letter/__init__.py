"""Letter template integration for Texsmith."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.core.templates import TemplateError, WrappableTemplate


_PACKAGE_ROOT = Path(__file__).parent.resolve()


@dataclass(frozen=True)
class LanguageProfile:
    """Describe locale-specific behaviour for the letter template."""

    key: str
    locale: str
    babel: str
    fallback_opening: str
    fallback_closing: str
    default_standard: str
    subject_prefix: str


@dataclass(frozen=True)
class LetterStandard:
    """Describe one of the supported national letter layouts."""

    key: str
    option: str


_LETTER_STANDARDS: dict[str, LetterStandard] = {
    "din": LetterStandard(key="din", option="DIN"),
    "sn-left": LetterStandard(key="sn-left", option="SNleft"),
    "sn-right": LetterStandard(key="sn-right", option="SNright"),
}

_LETTER_STANDARD_ALIASES: dict[str, str] = {
    "din": "din",
    "din5008": "din",
    "din-5008": "din",
    "de": "din",
    "german": "din",
    "sn": "sn-left",
    "sn010130": "sn-left",
    "sn-010130": "sn-left",
    "snleft": "sn-left",
    "sn-left": "sn-left",
    "snright": "sn-right",
    "sn-right": "sn-right",
    "swiss": "sn-left",
}


_LANGUAGE_PROFILES: dict[str, LanguageProfile] = {
    "en-uk": LanguageProfile(
        key="en-uk",
        locale="en-UK",
        babel="british",
        fallback_opening="Dear Sir or Madam,",
        fallback_closing="Yours faithfully,",
        default_standard="din",
        subject_prefix=r"Subject:~",
    ),
    "en-us": LanguageProfile(
        key="en-us",
        locale="en-US",
        babel="english",
        fallback_opening="Dear Sir or Madam,",
        fallback_closing="Sincerely,",
        default_standard="din",
        subject_prefix=r"Subject:~",
    ),
    "fr-fr": LanguageProfile(
        key="fr-fr",
        locale="fr-FR",
        babel="french",
        fallback_opening="Madame, Monsieur,",
        fallback_closing="Je vous prie d’agréer l’expression de mes salutations distinguées.",
        default_standard="sn-left",
        subject_prefix=r"Objet~:~",
    ),
}


class Template(WrappableTemplate):
    """Expose the formal letter template as a wrappable template."""

    def __init__(self) -> None:
        try:
            super().__init__(_PACKAGE_ROOT)
        except TemplateError as exc:
            raise TemplateError(f"Failed to initialise letter template: {exc}") from exc

    def prepare_context(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = super().prepare_context(latex_body, overrides=overrides)

        profile = self._resolve_language_profile(context.get("language"))
        context["language"] = profile.locale
        context["babel_language"] = profile.babel
        letter_standard = self._resolve_letter_standard(
            context.get("standard")
            or context.get("letter_standard")
            or context.get("layout"),
            profile,
        )
        context["letter_standard"] = letter_standard.key
        context["letter_standard_option"] = letter_standard.option

        context["from_name"] = self._coerce_string(context.get("from_name")) or ""
        context["signature_text"] = (
            self._coerce_string(context.get("signature")) or context["from_name"]
        )

        context["from_address_lines"] = self._inject_name_line(
            self._normalise_lines(context.get("from_address")),
            context["from_name"],
        )
        context["to_address_lines"] = self._inject_name_line(
            self._normalise_lines(context.get("to_address")),
            context["to_name"],
        )

        context["opening_text"] = self._resolve_opening(context, profile)
        context["closing_text"] = self._resolve_closing(context, profile)
        context["date_value"] = self._coerce_string(context.get("date")) or r"\today"
        context["object_value"] = self._coerce_string(context.get("object")) or ""
        context["from_location_value"] = self._coerce_string(context.get("from_location")) or ""
        context["to_name"] = self._coerce_string(context.get("to_name")) or ""
        context["subject_prefix"] = profile.subject_prefix

        context["signature_text"] = context["signature_text"] or context["from_name"]
        if not context["signature_text"]:
            raise TemplateError("Sender name is required to compute the letter signature.")

        context["has_subject"] = bool(context["object_value"])
        context["has_sender_address"] = bool(context["from_address_lines"])
        context["has_recipient_address"] = bool(context["to_address_lines"])
        context["use_cursive_signature"] = bool(context.get("cursive"))
        fold_marks = bool(context.get("fold_marks"))
        context["fold_marks_enabled"] = fold_marks
        context["foldmarks_option"] = "true" if fold_marks else "false"

        context.pop("press", None)
        context["callout_style"] = self._normalise_callout_style(context.get("callout_style"))

        return context

    def _resolve_letter_standard(self, value: Any, profile: LanguageProfile) -> LetterStandard:
        candidate = self._coerce_string(value)
        if candidate:
            key = candidate.lower().replace(" ", "-").replace("_", "-").replace(".", "-")
        else:
            key = profile.default_standard
        resolved_key = _LETTER_STANDARD_ALIASES.get(key, key)
        if resolved_key in _LETTER_STANDARDS:
            return _LETTER_STANDARDS[resolved_key]
        return _LETTER_STANDARDS[profile.default_standard]

    def _resolve_language_profile(self, value: Any) -> LanguageProfile:
        if isinstance(value, str):
            key = value.strip().lower().replace("_", "-")
        else:
            key = ""

        if not key:
            return _LANGUAGE_PROFILES["en-uk"]

        alias_map = {
            "en": "en-uk",
            "en-gb": "en-uk",
            "english": "en-uk",
            "english-gb": "en-uk",
            "en-us": "en-us",
            "english-us": "en-us",
            "us": "en-us",
            "fr": "fr-fr",
            "fr-ca": "fr-fr",
            "fr-ch": "fr-fr",
        }
        resolved_key = alias_map.get(key, key)

        if resolved_key not in _LANGUAGE_PROFILES:
            if resolved_key.startswith("fr"):
                resolved_key = "fr-fr"
            elif resolved_key.startswith("en-us"):
                resolved_key = "en-us"
            elif resolved_key.startswith("en"):
                resolved_key = "en-uk"
            else:
                resolved_key = "en-uk"

        return _LANGUAGE_PROFILES[resolved_key]

    def _coerce_string(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            candidate = value.strip()
        else:
            candidate = str(value).strip()
        return candidate or None

    def _normalise_lines(self, payload: Any) -> list[str]:
        if payload is None:
            return []
        if isinstance(payload, str):
            tokens = [line.strip() for line in payload.replace("\r", "").splitlines()]
            lines = [escape_latex_chars(token) for token in tokens if token]
            return lines
        if isinstance(payload, Mapping):
            lines: list[str] = []
            for _, raw_value in payload.items():
                candidate = self._coerce_string(raw_value)
                if candidate:
                    lines.append(escape_latex_chars(candidate))
            return lines
        if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
            lines = []
            for item in payload:
                if isinstance(item, Mapping):
                    lines.extend(self._normalise_lines(item))
                    continue
                candidate = self._coerce_string(item)
                if candidate:
                    lines.append(escape_latex_chars(candidate))
            return lines
        candidate = self._coerce_string(payload)
        return [escape_latex_chars(candidate)] if candidate else []

    def _inject_name_line(self, lines: list[str], name: str) -> list[str]:
        if not name:
            return lines
        if lines and lines[0] == name:
            return lines
        return [name] + lines

    def _resolve_opening(self, context: Mapping[str, Any], profile: LanguageProfile) -> str:
        opening_override = self._coerce_string(context.get("opening"))
        if opening_override:
            return opening_override
        title_value = self._coerce_string(context.get("title"))
        if title_value:
            return title_value
        return ""

    def _resolve_closing(self, context: Mapping[str, Any], profile: LanguageProfile) -> str:
        closing_override = self._coerce_string(context.get("closing"))
        if closing_override:
            return closing_override
        return profile.fallback_closing

    def _normalise_callout_style(self, value: Any) -> str:
        candidate = self._coerce_string(value)
        if candidate:
            candidate = candidate.lower()
        else:
            candidate = "fancy"
        if candidate not in {"fancy", "classic", "minimal"}:
            return "fancy"
        return candidate
