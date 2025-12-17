from texsmith.fonts.coverage import NotoCoverage
from texsmith.fonts.fallback import FallbackBuilder
from texsmith.fonts.ucharclasses import UCharClass
from texsmith.fragments.fonts import _prepare_fallback_context


def test_fallback_aligns_with_usage_slug(tmp_path, monkeypatch) -> None:
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    # Provide minimal font files so lookup succeeds without downloads.
    for name in (
        "NotoSansSC-Regular.otf",
        "NotoSansSC-Bold.otf",
        "NotoKufiArabic-Regular.otf",
        "NotoKufiArabic-Bold.otf",
    ):
        (fonts_dir / name).write_bytes(b"0")

    # Avoid network fetches during tests.
    monkeypatch.setattr(
        "texsmith.fragments.fonts.NotoFontDownloader.ensure",
        lambda self, *, font_name, styles, extension, dir_base=None: None,  # noqa: ARG005
    )

    context = {
        "fonts": {
            "fallback_summary": [
                {
                    "group": "Chinese",
                    "class": "CJKUnifiedIdeographs",
                    "font": {
                        "name": "NotoSansSC",
                        "styles": ["regular", "bold"],
                        "extension": ".otf",
                    },
                    "count": 2,
                }
            ],
            "script_usage": [
                {
                    "group": "Chinese",
                    "slug": "chinese",
                    "font_name": "NotoSansSC",
                    "font_command": "chinesefont",
                    "text_command": "textchinese",
                    "count": 2,
                }
            ],
        }
    }

    result = _prepare_fallback_context(context, output_dir=tmp_path)

    entries = result["entries"]
    assert entries and entries[0]["slug"] == "chinese"
    assert entries[0]["font_command"] == "chinesefont"
    assert entries[0]["text_command"] == "textchinese"
    assert "textchinese" not in result["missing_commands"]
    assert result["transitions"] == [
        r"\setTransitionsFor{CJKUnifiedIdeographs}{\chinesefont}{\texsmithFallbackFamily}"
    ]


def test_all_classes_for_slug_receive_transitions(tmp_path, monkeypatch) -> None:
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    for name in ("NotoSansSC-Regular.otf", "NotoSansSC-Bold.otf"):
        (fonts_dir / name).write_bytes(b"0")

    monkeypatch.setattr(
        "texsmith.fragments.fonts.NotoFontDownloader.ensure",
        lambda self, *, font_name, styles, extension, dir_base=None: None,  # noqa: ARG005
    )

    context = {
        "fonts": {
            "fallback_summary": [
                {
                    "group": "Chinese",
                    "class": "CJKUnifiedIdeographs",
                    "font": {
                        "name": "NotoSansSC",
                        "styles": ["regular", "bold"],
                        "extension": ".otf",
                    },
                    "count": 2,
                },
                {
                    "group": "Chinese",
                    "class": "CJKSymbolsAndPunctuation",
                    "font": {
                        "name": "NotoSansSC",
                        "styles": ["regular", "bold"],
                        "extension": ".otf",
                    },
                    "count": 1,
                },
            ],
            "script_usage": [
                {
                    "group": "Chinese",
                    "slug": "chinese",
                    "font_name": "NotoSansSC",
                    "font_command": "chinesefont",
                    "text_command": "textchinese",
                    "count": 3,
                }
            ],
        }
    }

    result = _prepare_fallback_context(context, output_dir=tmp_path)

    assert result["transitions"] == [
        r"\setTransitionsFor{CJKSymbolsAndPunctuation}{\chinesefont}{\texsmithFallbackFamily}",
        r"\setTransitionsFor{CJKUnifiedIdeographs}{\chinesefont}{\texsmithFallbackFamily}",
    ]


def test_usage_font_preferred_over_stale_entries(tmp_path, monkeypatch) -> None:
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    for name in (
        "NotoSansSC-Regular.otf",
        "NotoSansSC-Bold.otf",
        "NotoKufiArabic-Regular.otf",
        "NotoKufiArabic-Bold.otf",
    ):
        (fonts_dir / name).write_bytes(b"0")

    monkeypatch.setattr(
        "texsmith.fragments.fonts.NotoFontDownloader.ensure",
        lambda self, *, font_name, styles, extension, dir_base=None: None,  # noqa: ARG005
    )

    context = {
        "fonts": {
            # Stale summary entry with an overly generic font.
            "fallback_summary": [
                {
                    "group": "Arabics",
                    "class": "Arabic",
                    "font": {
                        "name": "NotoSansSC",
                        "styles": ["regular", "bold"],
                        "extension": ".otf",
                    },
                    "count": 10,
                },
                # Fresh entry with the correct font.
                {
                    "group": "Arabics",
                    "class": "Arabic",
                    "font": {
                        "name": "NotoKufiArabic",
                        "styles": ["regular", "bold"],
                        "extension": ".otf",
                    },
                    "count": 5,
                },
            ],
            "script_usage": [
                {
                    "group": "Arabics",
                    "slug": "arabics",
                    "font_name": "NotoKufiArabic",
                    "font_command": "arabicsfont",
                    "text_command": "textarabics",
                    "count": 5,
                }
            ],
        }
    }

    result = _prepare_fallback_context(context, output_dir=tmp_path)
    arabic_entry = next(entry for entry in result["entries"] if entry["slug"] == "arabics")
    assert arabic_entry["font_name"] == "NotoKufiArabic"
    assert result["transitions"] == [
        r"\setTransitionsFor{Arabic}{\arabicsfont}{\texsmithFallbackFamily}"
    ]


def test_greek_prefers_font_with_styles() -> None:
    builder = FallbackBuilder()
    coverage = builder._prepare_coverage(
        [
            NotoCoverage(
                family="Noto Sans Display",
                ranges=((0x0370, 0x03FF),),
                file_base="NotoSansDisplay",
                dir_base="NotoSansDisplay",
                styles=(),
            ),
            NotoCoverage(
                family="Noto Serif",
                ranges=((0x0370, 0x03FF),),
                file_base="NotoSerif",
                dir_base="NotoSerif",
                styles=("regular", "bold"),
            ),
        ]
    )
    cls = UCharClass(name="GreekAndCoptic", start=0x0370, end=0x03FF, group="Greek")

    result = builder._pick_font(cls, coverage)

    assert result is not None
    assert result["name"] == "NotoSerif"


def test_devanagari_prefers_script_specific_font() -> None:
    builder = FallbackBuilder()
    coverage = builder._prepare_coverage(
        [
            NotoCoverage(
                family="Noto Sans",
                ranges=((0x0370, 0x03FF), (0x0900, 0x097F)),
                file_base="NotoSans",
                dir_base="NotoSans",
                styles=("regular", "bold", "italic", "bolditalic"),
            ),
            NotoCoverage(
                family="Noto Sans Devanagari",
                ranges=((0x0900, 0x097F),),
                file_base="NotoSansDevanagari",
                dir_base="NotoSansDevanagari",
                styles=("regular", "bold"),
            ),
        ]
    )
    cls = UCharClass(name="Devanagari", start=0x0900, end=0x097F, group="Devanagari")

    result = builder._pick_font(cls, coverage)

    assert result is not None
    assert result["name"] == "NotoSansDevanagari"
