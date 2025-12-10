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
    assert result["transitions"] == []


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
