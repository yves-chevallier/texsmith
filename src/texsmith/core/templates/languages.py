"""Language-tag mapping tables shared by the template layer.

Maps between BCP-47 language codes and babel language names (LaTeX) / ISO
primary subtags (Typst ``text(lang: …)``). Extracted from ``manifest`` so both
the manifest normalisers and ``runtime`` can consume the tables without one
reaching into the other.
"""

from __future__ import annotations


_BABEL_LANGUAGE_ALIASES = {
    "ad": "catalan",
    "ca": "catalan",
    "cs": "czech",
    "da": "danish",
    "de": "ngerman",
    "de-de": "ngerman",
    "en": "english",
    "en-gb": "british",
    "en-us": "english",
    "en-au": "australian",
    "en-ca": "canadian",
    "es": "spanish",
    "es-es": "spanish",
    "es-mx": "mexican",
    "fi": "finnish",
    "fr": "french",
    "fr-fr": "french",
    "fr-ca": "canadien",
    "it": "italian",
    "nl": "dutch",
    "nb": "norwegian",
    "nn": "nynorsk",
    "pl": "polish",
    "pt": "portuguese",
    "pt-br": "brazilian",
    "ro": "romanian",
    "ru": "russian",
    "sk": "slovak",
    "sl": "slovene",
    "sv": "swedish",
    "tr": "turkish",
}


def _map_babel_language(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    lowered = candidate.lower().replace("_", "-")
    if lowered in _BABEL_LANGUAGE_ALIASES:
        return _BABEL_LANGUAGE_ALIASES[lowered]
    primary = lowered.split("-", 1)[0]
    if primary in _BABEL_LANGUAGE_ALIASES:
        return _BABEL_LANGUAGE_ALIASES[primary]
    if lowered.isalpha():
        return lowered
    return None


# Babel language names -> BCP-47 primary subtag (the inverse view of
# ``_BABEL_LANGUAGE_ALIASES``, which maps codes -> babel names). Used by the
# Typst backend, whose ``text(lang: …)`` wants an ISO 639 code.
_BCP47_FROM_BABEL: dict[str, str] = {
    "english": "en",
    "british": "en",
    "american": "en",
    "australian": "en",
    "canadian": "en",
    "usenglish": "en",
    "ukenglish": "en",
    "french": "fr",
    "francais": "fr",
    "canadien": "fr",
    "acadian": "fr",
    "german": "de",
    "ngerman": "de",
    "austrian": "de",
    "naustrian": "de",
    "spanish": "es",
    "mexican": "es",
    "italian": "it",
    "dutch": "nl",
    "portuguese": "pt",
    "brazilian": "pt",
    "russian": "ru",
    "polish": "pl",
    "czech": "cs",
    "slovak": "sk",
    "slovene": "sl",
    "danish": "da",
    "swedish": "sv",
    "finnish": "fi",
    "norwegian": "nb",
    "nynorsk": "nn",
    "catalan": "ca",
    "romanian": "ro",
    "turkish": "tr",
}


def _map_bcp47_language(value: str | None) -> str | None:
    """Resolve ``value`` to a BCP-47 primary subtag (babel name or code in)."""
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    lowered = candidate.lower().replace("_", "-")
    if lowered in _BCP47_FROM_BABEL:
        return _BCP47_FROM_BABEL[lowered]
    primary = lowered.split("-", 1)[0]
    if primary in _BCP47_FROM_BABEL:
        return _BCP47_FROM_BABEL[primary]
    # Already an ISO 639 code (e.g. "en", "fr", "en-gb" -> "en").
    if 2 <= len(primary) <= 3 and primary.isalpha():
        return primary
    return None


__all__ = [
    "_BABEL_LANGUAGE_ALIASES",
    "_BCP47_FROM_BABEL",
    "_map_babel_language",
    "_map_bcp47_language",
]
