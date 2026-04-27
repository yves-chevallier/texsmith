"""Resolve the document ``date`` front-matter into canonical text.

Accepted shapes:

- ``None`` or absent → empty string (``\\date{}`` — title block omits the date);
- ``"none"`` (case-insensitive) → empty string (explicit "no date");
- ``"today"`` (case-insensitive) → today's date in long form, localised;
- ``"commit"`` (case-insensitive) → date of the most recent ``HEAD`` commit;
- a YAML date or ``"YYYY-MM-DD"`` string → long-form rendering localised by
  the document ``language`` (e.g. ``"5 mars 2026"`` for ``language: french``);
- any other free-form string → returned trimmed (the user already wrote what
  they want).

Long-form rendering currently supports French and English month names; other
languages fall back to English. The renderer is independent of the article
template so other templates can opt in by importing :func:`format_date`.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
import warnings


__all__ = ["format_date"]


_FRENCH_MONTHS = (
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
)

_ENGLISH_MONTHS = (
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
)

# Babel language names (see article manifest ``language`` attribute) mapped to
# the locale used for long-form rendering. Keys are lowercase to match the
# normaliser output. Unknown languages fall back to English.
_LANGUAGE_TO_LOCALE: dict[str, str] = {
    "french": "fr",
    "francais": "fr",
    "français": "fr",
    "fr": "fr",
    "fr-fr": "fr",
    "fr-ch": "fr",
    "english": "en",
    "british": "en",
    "american": "en",
    "en": "en",
    "en-us": "en",
    "en-uk": "en",
    "en-gb": "en",
    "ngerman": "en",  # No FR/DE month tables yet — degrade gracefully.
    "german": "en",
}


def format_date(
    value: Any,
    *,
    language: Any = None,
    cwd: Path | None = None,
    today: date | None = None,
) -> str:
    """Resolve the front-matter ``date`` value and return canonical text.

    ``today`` is exposed as a parameter so tests can inject a deterministic
    value; production callers omit it and pick up the system date.
    """
    if value is None:
        return ""

    locale = _resolve_locale(language)

    if isinstance(value, datetime):
        return _render_date(value.date(), locale)
    if isinstance(value, date):
        return _render_date(value, locale)

    if isinstance(value, str):
        return _resolve_string(value, locale=locale, cwd=cwd, today=today)

    raise TypeError(
        f"date field has unsupported type {type(value).__name__}; "
        "expected string, date, or omitted."
    )


def _resolve_string(
    value: str,
    *,
    locale: str,
    cwd: Path | None,
    today: date | None,
) -> str:
    text = value.strip()
    if not text:
        return ""
    keyword = text.lower()
    if keyword == "none":
        return ""
    if keyword == "today":
        return _render_date(today or date.today(), locale)  # noqa: DTZ011
    if keyword == "commit":
        from texsmith.core.git_version import git_commit_date

        commit = git_commit_date(cwd=cwd)
        if commit is None:
            return ""
        return _render_date(commit, locale)

    parsed = _parse_iso(text)
    if parsed is not None:
        return _render_date(parsed, locale)
    return text


def _parse_iso(value: str) -> date | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.date()


def _render_date(value: date, locale: str) -> str:
    months = _FRENCH_MONTHS if locale == "fr" else _ENGLISH_MONTHS
    month = months[value.month - 1]
    if locale == "fr":
        day = "1er" if value.day == 1 else str(value.day)
        return f"{day} {month} {value.year}"
    return f"{month} {value.day}, {value.year}"


def _resolve_locale(language: Any) -> str:
    if language is None:
        return "en"
    if not isinstance(language, str):
        warnings.warn(
            f"date renderer ignoring non-string language={language!r}; using English.",
            stacklevel=3,
        )
        return "en"
    key = language.strip().lower()
    return _LANGUAGE_TO_LOCALE.get(key, "en")
