from pathlib import Path

from texsmith.api import match_fonts
from texsmith.fonts.analyzer import analyse_font_requirements


def _write_demo_fonts_yaml(tmp_path: Path) -> Path:
    payload = """\
- family: DemoSans
  unicode_ranges:
    - [0x0041, 0x005A]
    - [0x0061, 0x007A]
- family: DemoEmoji
  unicode_ranges:
    - [0x1F600, 0x1F601]
"""
    path = tmp_path / "fonts.yaml"
    path.write_text(payload, encoding="utf-8")
    return path


def test_match_fonts_with_custom_index(tmp_path: Path) -> None:
    fonts_yaml = _write_demo_fonts_yaml(tmp_path)
    result = match_fonts("Ab😀", fonts_yaml=fonts_yaml, check_system=False)

    # ASCII characters are covered by the base font stack; only the emoji requires a fallback.
    assert set(result.fallback_fonts) == {"DemoEmoji"}
    assert not result.missing_fonts
    assert not result.missing_codepoints


def test_ascii_prefers_generic_noto(tmp_path: Path) -> None:
    fonts_yaml = tmp_path / "fonts.yaml"
    fonts_yaml.write_text(
        """\
- family: NotoSans
  unicode_ranges:
    - [0x0041, 0x005A]
    - [0x0061, 0x007A]
- family: NotoSansInscriptionalParthian
  unicode_ranges:
    - [0x0000, 0x007F]
""",
        encoding="utf-8",
    )

    result = match_fonts("Ab", fonts_yaml=fonts_yaml, check_system=False)

    # ASCII is handled by the primary font stack, so no fallbacks are required.
    assert result.fallback_fonts == ()


def test_font_analysis_collects_nested_characters(tmp_path: Path) -> None:
    fonts_yaml = _write_demo_fonts_yaml(tmp_path)
    slot_outputs = {"mainmatter": "A"}
    context = {"title": "😀", "nested": {"note": ["b"]}}

    result = analyse_font_requirements(
        slot_outputs=slot_outputs,
        context=context,
        fonts_yaml=fonts_yaml,
        check_system=False,
    )

    assert result is not None
    # Only the emoji needs a dedicated fallback font.
    assert set(result.fallback_fonts) == {"DemoEmoji"}


def test_cjk_scripts_map_to_cjk_fonts() -> None:
    result = match_fonts("漢字かなカナ한글", check_system=False)
    assert "NotoSansCJKsc" in result.fallback_fonts
    assert "NotoSerifCJKjp" in result.fallback_fonts
    assert "NotoSerifCJKkr" in result.fallback_fonts
    assert "chinese" in result.script_blocks
    assert "japanese" in result.script_blocks
    assert "korean" in result.script_blocks
