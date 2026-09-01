from texsmith.fonts.coverage import NotoCoverage
from texsmith.fonts.fallback import FallbackBuilder
from texsmith.fonts.provisioning import _prepare_fallback_context
from texsmith.fonts.ucharclasses import UCharClass


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
        "texsmith.fonts.provisioning.NotoFontDownloader.ensure",
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
        "texsmith.fonts.provisioning.NotoFontDownloader.ensure",
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
        "texsmith.fonts.provisioning.NotoFontDownloader.ensure",
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


def _render_fonts_fragment(**context) -> str:
    """Render the ``ts-fonts`` fragment template with a minimal context."""
    from pathlib import Path

    from texsmith.core.templates.base import _build_environment

    root = Path(__file__).resolve().parents[1] / "src" / "texsmith" / "fragments" / "fonts"
    return _build_environment(root).get_template("ts-fonts.jinja.sty").render(**context)


_GREEK_FALLBACK = {
    "family": "lm",
    "fallback": {
        "entries": [
            {
                "font_command": "greekfont",
                "text_command": "textgreek",
                "font_name": "NotoSans",
                "extension": ".otf",
                "path": "fonts",
                "upright": "NotoSans-Regular",
                "bold": "NotoSans-Bold",
                "has_bold": True,
            }
        ],
        "transitions": [r"\setTransitionsFor{GreekAndCoptic}{\greekfont}{\texsmithFallbackFamily}"],
        "package_options": ["GreekAndCoptic"],
    },
}


def test_xetex_transitions_restore_math_footnote_symbols() -> None:
    """Footnote marks must survive the ucharclasses transitions.

    Since 2020 the LaTeX kernel builds them from text symbols
    (``\\textasteriskcentered`` -> U+2217, ``\\textdagger`` -> U+2020). Those
    codepoints sit in blocks a transition may hand over to a fallback font
    picked for *other* characters of the same block — a font that need not
    carry the mark glyphs, in which case the mark silently disappears.
    """
    rendered = _render_fonts_fragment(fonts_family="lm", fonts=_GREEK_FALLBACK)

    assert r"\setTransitionsFor{GreekAndCoptic}" in rendered
    assert r"\renewcommand\@fnsymbol" in rendered
    # The marks must come from the math font, out of reach of the transitions.
    assert r"\ensuremath{%" in rendered
    guard = rendered.index(r"\renewcommand\@fnsymbol")
    assert guard > rendered.index(r"\setTransitionsFor{GreekAndCoptic}")


def test_no_footnote_guard_without_fallback_transitions() -> None:
    # No transition installed, no hijacking possible: the kernel definition
    # is left alone.
    rendered = _render_fonts_fragment(fonts_family="lm", fonts={"family": "lm"})

    assert r"\setTransitionsFor" not in rendered
    assert r"\@fnsymbol" not in rendered


def test_capital_greek_survives_math_alphabets() -> None:
    """``\\mathrm{k\\Omega}`` must not lose its Omega under fontspec.

    fontspec keeps the legacy OT1 math layout in a ``legacymaths`` symbol font
    where capital Greek sits in slots "00-"0A, but declares those symbols
    ``\\mathalpha``: a math alphabet then refetches them from the *current*
    alphabet font — a Unicode text font whose low slots hold control
    characters — and the glyph silently vanishes (``Missing character:
    U+000A``). The fragment redeclares them ``\\mathord`` so they always come
    from ``legacymaths``, with or without fallback transitions.
    """
    for rendered in (
        _render_fonts_fragment(fonts_family="lm"),
        _render_fonts_fragment(fonts_family="lm", fonts=_GREEK_FALLBACK),
    ):
        assert r'\DeclareMathSymbol{\Omega}{\mathord}{legacymaths}{"0A}' in rendered
        assert r'\DeclareMathSymbol{\Gamma}{\mathord}{legacymaths}{"00}' in rendered
        # Deferred so it lands after fontspec's own hook-deferred math setup,
        # and skipped cleanly when fontspec was loaded with no-math.
        declaration = rendered.index(r"\DeclareMathSymbol{\Omega}")
        hook = rendered.rindex(r"\AtBeginDocument{%", 0, declaration)
        assert r"\@ifundefined{symlegacymaths}" in rendered[hook:declaration]
