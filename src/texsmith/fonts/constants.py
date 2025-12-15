"""Shared constants and helpers for Noto font handling."""

from __future__ import annotations


_STYLE_SUFFIXES = {
    "regular": "Regular",
    "italic": "Italic",
    "bold": "Bold",
    "bolditalic": "BoldItalic",
}

_CJK_PATHS = {
    "jp": "Sans/OTF/Japanese/",
    "kr": "Sans/OTF/Korean/",
    "sc": "Sans/OTF/SimplifiedChinese/",
    "tc": "Sans/OTF/TraditionalChinese/",
    "hk": "Sans/OTF/TraditionalChineseHK/",
}

CJK_ALIASES = {
    "NotoSansJP": ("NotoSansCJKjp", _CJK_PATHS["jp"]),
    "NotoSansKR": ("NotoSansCJKkr", _CJK_PATHS["kr"]),
    "NotoSansSC": ("NotoSansCJKsc", _CJK_PATHS["sc"]),
    "NotoSansTC": ("NotoSansCJKtc", _CJK_PATHS["tc"]),
    "NotoSansHK": ("NotoSansCJKhk", _CJK_PATHS["hk"]),
}


def style_suffix(style: str) -> str:
    """Return the canonical filename suffix for a Noto style."""
    return _STYLE_SUFFIXES.get(style.lower(), style.title())


def filename_base(filename: str) -> str:
    """Return the base name of a Noto font file, stripping style suffixes."""
    return filename.split("-")[0]


def guess_cjk_path(filename: str) -> str:
    """Guess the CJK subpath for a Noto CJK font filename."""
    base = filename_base(filename)
    if base in CJK_ALIASES:
        return CJK_ALIASES[base][1]

    lowered = base.lower()
    if "cjkjp" in lowered:
        return _CJK_PATHS["jp"]
    if "cjkkr" in lowered:
        return _CJK_PATHS["kr"]
    if "cjksc" in lowered:
        return _CJK_PATHS["sc"]
    if "cjktc" in lowered:
        return _CJK_PATHS["tc"]
    if "cjkhk" in lowered:
        return _CJK_PATHS["hk"]
    return ""


__all__ = ["CJK_ALIASES", "filename_base", "guess_cjk_path", "style_suffix"]
