"""Metadata for manual CJK fallback handling."""

from __future__ import annotations


CJK_SCRIPT_ROWS = {
    "chinese": (
        "chinese",
        "Noto CJK Chinese",
        "NotoSansCJKsc",
        "NotoSansCJKsc",
        None,
        None,
    ),
    "japanese": (
        "japanese",
        "Noto CJK Japanese",
        "NotoSerifCJKjp",
        "NotoSerifCJKjp",
        None,
        None,
    ),
    "korean": (
        "korean",
        "Noto CJK Korean",
        "NotoSerifCJKkr",
        "NotoSerifCJKkr",
        None,
        None,
    ),
}

CJK_FAMILY_SPECS = {
    "NotoSansCJKsc": {
        "style_dir": "Sans",
        "region": "SimplifiedChinese",
        "suffix": "sc",
        "weights": ("Regular", "Bold"),
    },
    "NotoSansCJKjp": {
        "style_dir": "Sans",
        "region": "Japanese",
        "suffix": "jp",
        "weights": ("Regular", "Bold"),
    },
    "NotoSansCJKkr": {
        "style_dir": "Sans",
        "region": "Korean",
        "suffix": "kr",
        "weights": ("Regular", "Bold"),
    },
    "NotoSerifCJKsc": {
        "style_dir": "Serif",
        "region": "SimplifiedChinese",
        "suffix": "sc",
        "weights": ("Regular", "Bold"),
    },
    "NotoSerifCJKjp": {
        "style_dir": "Serif",
        "region": "Japanese",
        "suffix": "jp",
        "weights": ("Regular", "Bold"),
    },
    "NotoSerifCJKkr": {
        "style_dir": "Serif",
        "region": "Korean",
        "suffix": "kr",
        "weights": ("Regular", "Bold"),
    },
}

CJK_BLOCK_OVERRIDES = {
    # Chinese and Han ideographs
    "CJKUnifiedIdeographs": "chinese",
    "CJKUnifiedIdeographsExtensionA": "chinese",
    "CJKUnifiedIdeographsExtensionB": "chinese",
    "CJKUnifiedIdeographsExtensionC": "chinese",
    "CJKUnifiedIdeographsExtensionD": "chinese",
    "CJKUnifiedIdeographsExtensionE": "chinese",
    "CJKUnifiedIdeographsExtensionF": "chinese",
    "CJKUnifiedIdeographsExtensionG": "chinese",
    "CJKUnifiedIdeographsExtensionH": "chinese",
    "CJKCompatibility": "chinese",
    "CJKCompatibilityForms": "chinese",
    "CJKCompatibilityIdeographs": "chinese",
    "CJKCompatibilityIdeographsSupplement": "chinese",
    "CJKRadicalsSupplement": "chinese",
    "CJKStrokes": "chinese",
    "CJKSymbolsAndPunctuation": "chinese",
    "IdeographicDescriptionCharacters": "chinese",
    "IdeographicSymbolsAndPunctuation": "chinese",
    "KangxiRadicals": "chinese",
    "Bopomofo": "chinese",
    "BopomofoExtended": "chinese",
    "HangulCompatibilityJamo": "korean",
    "HangulJamo": "korean",
    "HangulJamoExtendedA": "korean",
    "HangulJamoExtendedB": "korean",
    "HangulSyllables": "korean",
    "Hiragana": "japanese",
    "Katakana": "japanese",
    "KatakanaPhoneticExtensions": "japanese",
    "KanaExtendedA": "japanese",
    "KanaExtendedB": "japanese",
    "KanaSupplement": "japanese",
    "Kanbun": "japanese",
    "SmallKanaExtension": "japanese",
}

__all__ = ["CJK_BLOCK_OVERRIDES", "CJK_FAMILY_SPECS", "CJK_SCRIPT_ROWS"]
