"""Letter template integration for Texsmith."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone


try:
    from datetime import UTC  # py311+ noqa: F401
except ImportError:  # pragma: no cover - py310 compatibility
    UTC = timezone.utc
import logging
from pathlib import Path
import re
import shutil
from typing import Any, ClassVar

from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.adapters.transformers import svg2pdf
from texsmith.core.exceptions import TransformerExecutionError
from texsmith.core.templates import TemplateError, WrappableTemplate


_PACKAGE_ROOT = Path(__file__).parent.resolve()
_log = logging.getLogger(__name__)


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
    "nf": LetterStandard(key="nf", option="NF"),
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
    "nf": "nf",
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
        fallback_closing="Je vous prie d'agreer l'expression de mes salutations distinguees.",
        default_standard="sn-left",
        subject_prefix=r"Objet~:~",
    ),
}

_EN_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

_FR_MONTHS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


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
        context["ts_extra_disable_hyperref"] = True

        profile = self._resolve_language_profile(context.get("language"))
        context["language"] = profile.locale
        context["babel_language"] = profile.babel
        letter_standard = self._resolve_letter_standard(
            context.get("standard") or context.get("letter_standard") or context.get("layout"),
            profile,
        )
        context["letter_standard"] = letter_standard.key
        context["letter_standard_option"] = letter_standard.option

        context["from_name"] = self._coerce_string(context.get("from_name")) or ""
        context["to_name"] = self._coerce_string(context.get("to_name")) or ""
        signature_payload = context.get("signature")
        signature_text_hint, signature_image_hint = self._extract_signature_components(
            signature_payload
        )
        from_lines = self._normalise_lines(context.get("from_address"))
        to_lines = self._normalise_lines(context.get("to_address"))
        context["from_address_lines"] = from_lines
        context["to_address_lines"] = self._inject_name_line(to_lines, context["to_name"])
        back_address_lines = self._normalise_lines(context.get("back_address"))
        context["back_address_lines"] = back_address_lines
        context["has_back_address"] = bool(back_address_lines)
        context["has_sender_address"] = bool(from_lines)
        context["has_recipient_address"] = bool(context["to_address_lines"])

        cleaned_body = self._strip_plain_pagestyle(latex_body)
        closing_override = self._coerce_string(context.get("closing"))
        body_without_closing = cleaned_body
        inferred_closing: str | None = closing_override
        if not inferred_closing:
            body_without_closing, inferred_closing = self._extract_body_closing(cleaned_body)
        closing_text = inferred_closing or self._resolve_closing(context, profile)
        context["mainmatter"] = body_without_closing.strip()
        context["_texsmith_main_body"] = context["mainmatter"]
        context["closing_text"] = closing_text
        context["has_closing"] = bool(closing_text)

        context["opening_text"] = self._resolve_opening(context, profile)
        context["date_value"] = self._format_date_value(context.get("date"), profile)
        context["object_value"] = self._coerce_string(context.get("object")) or ""
        context["from_location_value"] = self._coerce_string(context.get("from_location")) or ""
        context["subject_prefix"] = profile.subject_prefix

        signature_image_path = self._resolve_signature_image(
            signature_image_hint or signature_text_hint,
            context,
        )
        if signature_image_path and signature_image_hint is None:
            signature_text_hint = None
        signature_text = signature_text_hint or context["from_name"]
        if not signature_text:
            raise TemplateError("Sender name is required to compute the letter signature.")
        context["signature_text"] = signature_text
        context["signature_image_path"] = signature_image_path
        context["has_signature_image"] = bool(signature_image_path)
        context["use_cursive_signature"] = bool(context.get("cursive"))
        context["signature_alignment_command"] = self._resolve_signature_alignment(
            context.get("signature_align")
        )

        context["has_subject"] = bool(context["object_value"])
        fold_marks = bool(context.get("fold_marks"))
        context["fold_marks_enabled"] = fold_marks
        context["foldmarks_option"] = "true" if fold_marks else "false"

        reference_value = self._coerce_string(context.get("reference")) or ""
        context["reference_value"] = reference_value
        context["reference_fields_enabled"] = bool(context.get("reference_fields"))
        postscript_text = self._coerce_string(context.get("postscript")) or ""
        context["postscript_text"] = postscript_text
        context["has_postscript"] = bool(postscript_text)

        context.pop("press", None)

        return context

    def wrap_document(
        self,
        latex_body: str,
        *,
        overrides: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        """Wrap the rendered body while honouring template-specific adjustments."""
        body_override = None
        if context is not None:
            body_override = context.get("_texsmith_main_body")
        return super().wrap_document(
            body_override or latex_body,
            overrides=overrides,
            context=context,
        )

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
        key = value.strip().lower().replace("_", "-") if isinstance(value, str) else ""

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
        candidate = value.strip() if isinstance(value, str) else str(value).strip()
        return candidate or None

    def _normalise_lines(self, payload: Any) -> list[str]:
        if payload is None:
            return []
        if isinstance(payload, str):
            return self._split_lines(payload)
        if isinstance(payload, Mapping):
            lines: list[str] = []
            for _, raw_value in payload.items():
                candidate = self._coerce_string(raw_value)
                if candidate:
                    lines.extend(self._split_lines(candidate))
            return lines
        if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
            lines = []
            for item in payload:
                if isinstance(item, Mapping):
                    lines.extend(self._normalise_lines(item))
                    continue
                candidate = self._coerce_string(item)
                if candidate:
                    lines.extend(self._split_lines(candidate))
            return lines
        candidate = self._coerce_string(payload)
        return self._split_lines(candidate) if candidate else []

    def _split_lines(self, value: str) -> list[str]:
        tokens = [line.strip() for line in value.replace("\r", "").splitlines()]
        return [escape_latex_chars(token) for token in tokens if token]

    def _inject_name_line(self, lines: list[str], name: str) -> list[str]:
        if not name:
            return lines
        if lines and lines[0] == name:
            return lines
        return [name, *lines]

    def _resolve_opening(self, context: Mapping[str, Any], profile: LanguageProfile) -> str:
        opening_override = self._coerce_string(context.get("opening"))
        if opening_override:
            return opening_override
        title_value = self._coerce_string(context.get("title"))
        if title_value:
            return title_value
        to_name = self._coerce_string(context.get("to_name"))
        if to_name:
            if profile.key.startswith("en"):
                return f"Dear {to_name},"
            return profile.fallback_opening
        return profile.fallback_opening

    def _resolve_closing(self, context: Mapping[str, Any], profile: LanguageProfile) -> str:
        closing_override = self._coerce_string(context.get("closing"))
        if closing_override:
            return closing_override
        return profile.fallback_closing

    def _strip_plain_pagestyle(self, payload: str) -> str:
        return re.sub(r"\\thispagestyle\{[^}]+\}\s*", "", payload).strip()

    def _extract_body_closing(self, payload: str) -> tuple[str, str | None]:
        blocks = list(payload.rstrip().split("\n\n"))
        for index in range(len(blocks) - 1, -1, -1):
            candidate = blocks[index].strip()
            if not candidate:
                continue
            if self._looks_like_closing_block(candidate):
                del blocks[index]
                remainder = "\n\n".join(blocks).strip()
                return (remainder, candidate)
            break
        return (payload, None)

    def _looks_like_closing_block(self, candidate: str) -> bool:
        if not candidate.endswith(","):
            return False
        if "\\\\" in candidate or "\\begin" in candidate or "\\end" in candidate:
            return False
        return not len(candidate.split()) > 16

    def _resolve_signature_alignment(self, value: Any) -> str:
        candidate = self._coerce_string(value)
        key = (candidate or "left").lower()
        mapping = {
            "left": r"\raggedleft",
            "right": r"\raggedright",
            "center": r"\centering",
            "centre": r"\centering",
        }
        return mapping.get(key, r"\raggedleft")

    _SIGNATURE_EXTENSIONS: ClassVar[set[str]] = {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".svg",
    }

    def _extract_signature_components(self, value: Any) -> tuple[str | None, str | None]:
        if isinstance(value, Mapping):
            text_candidate = value.get("text") or value.get("name")
            image_candidate = value.get("image") or value.get("path")
            return self._coerce_string(text_candidate), self._coerce_string(image_candidate)
        return self._coerce_string(value), None

    def _resolve_signature_image(
        self,
        value: Any,
        context: Mapping[str, Any],
    ) -> str | None:
        candidate = self._coerce_string(value)
        if not candidate:
            return None
        path = Path(candidate)
        suffix = path.suffix.lower()
        if suffix not in self._SIGNATURE_EXTENSIONS:
            return None
        source_dir = self._coerce_string(context.get("source_dir"))
        if not path.is_absolute():
            if not source_dir:
                return None
            path = (Path(source_dir) / path).resolve()
        if not path.exists():
            raise TemplateError(f"Signature asset '{path}' does not exist.")
        output_dir = self._coerce_string(context.get("output_dir"))
        if _log.isEnabledFor(logging.DEBUG):
            _log.debug(
                "Resolved signature asset",
                extra={
                    "candidate": candidate,
                    "resolved_path": str(path),
                    "output_dir": output_dir,
                },
            )
        mirrored = self._mirror_signature_asset(path, Path(output_dir)) if output_dir else path
        return self._format_latex_path(mirrored)

    def _mirror_signature_asset(self, source: Path, output_dir: Path) -> Path:
        output_dir = output_dir.resolve()
        asset_root = (output_dir / "assets" / "signatures").resolve()
        asset_root.mkdir(parents=True, exist_ok=True)
        suffix = source.suffix.lower()
        if suffix == ".svg":
            try:
                produced = svg2pdf(source, output_dir=asset_root)
            except TransformerExecutionError as exc:  # pragma: no cover - conversion failure
                raise TemplateError(
                    f"Failed to convert signature SVG '{source}' to PDF: {exc}"
                ) from exc
            result = produced
        else:
            target = asset_root / source.name
            shutil.copy2(source, target)
            result = target
        try:
            return result.relative_to(output_dir)
        except ValueError:
            return result

    def _format_latex_path(self, path: Path) -> str:
        posix = path.as_posix()
        return escape_latex_chars(posix)

    def _format_date_value(self, value: Any, profile: LanguageProfile) -> str:
        parsed = self._parse_date_value(value)
        if parsed is None:
            candidate = self._coerce_string(value)
            return escape_latex_chars(candidate) if candidate else r"\today"
        month_name = self._month_name(parsed.month, profile)
        if profile.key == "en-us":
            formatted = f"{month_name} {parsed.day}, {parsed.year}"
        else:
            formatted = f"{parsed.day} {month_name} {parsed.year}"
        return escape_latex_chars(formatted)

    def _parse_date_value(self, value: Any) -> date | None:
        candidate = self._coerce_string(value)
        if not candidate:
            return None
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            formats = ("%Y/%m/%d", "%d/%m/%Y", "%d.%m.%Y", "%m/%d/%Y")
            for fmt in formats:
                try:
                    parsed = datetime.strptime(candidate, fmt).replace(tzinfo=UTC)
                    break
                except ValueError:
                    continue
            else:
                return None
        return parsed.date()

    def _month_name(self, month_index: int, profile: LanguageProfile) -> str:
        names = _FR_MONTHS if profile.key.startswith("fr") else _EN_MONTHS
        if 1 <= month_index <= 12:
            return names[month_index - 1]
        return names[0]
