from pathlib import Path

from texsmith.fonts.manager import prepare_fonts_for_context
from texsmith.fonts.locator import FontLocator
from texsmith.fonts.matcher import match_text


def _write_font(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")  # Empty payloads are enough for copy tests.


def test_font_locator_uses_fonts_yaml_and_copies(tmp_path: Path) -> None:
    font_dir = tmp_path / "fonts"
    regular = font_dir / "DemoSans-Regular.otf"
    bold = font_dir / "DemoSans-Bold.otf"
    italic = font_dir / "DemoSans-Italic.otf"
    for entry in (regular, bold, italic):
        _write_font(entry)

    fonts_yaml = tmp_path / "fonts.yaml"
    fonts_yaml.write_text(
        """\
- family: DemoSans
  files:
    - fonts/DemoSans-Regular.otf
    - fonts/DemoSans-Bold.otf
    - fonts/DemoSans-Italic.otf
  unicode_ranges:
    - [0x0041, 0x0042]
""",
        encoding="utf-8",
    )

    locator = FontLocator(fonts_yaml=fonts_yaml)
    located = locator.locate_family("DemoSans")
    assert located.regular == regular
    assert located.bold == bold
    assert located.italic == italic

    copied = locator.copy_families(["DemoSans"], tmp_path / "out" / "fonts")
    copied_font = copied["DemoSans"]
    assert (tmp_path / "out" / "fonts" / copied_font.regular.name).exists()
    assert (tmp_path / "out" / "fonts" / copied_font.bold.name).exists()
    assert (tmp_path / "out" / "fonts" / copied_font.italic.name).exists()


def test_prepare_fonts_updates_context_and_ranges(tmp_path: Path) -> None:
    font_dir = tmp_path / "fonts"
    _write_font(font_dir / "DemoSans-Regular.otf")
    _write_font(font_dir / "DemoEmoji-Regular.otf")

    fonts_yaml = tmp_path / "fonts.yaml"
    fonts_yaml.write_text(
        """\
- family: DemoSans
  files: ["fonts/DemoSans-Regular.otf"]
  unicode_ranges:
    - [0x0041, 0x005A]
- family: DemoEmoji
  files: ["fonts/DemoEmoji-Regular.otf"]
  unicode_ranges:
    - [0x1F600, 0x1F601]
""",
        encoding="utf-8",
    )

    locator = FontLocator(fonts_yaml=fonts_yaml)
    match = match_text("Ab😀", fonts_yaml=fonts_yaml, check_system=False, font_locator=locator)
    context: dict[str, object] = {}
    result = prepare_fonts_for_context(
        template_context=context,
        output_dir=tmp_path / "build",
        font_match=match,
        font_locator=locator,
        emitter=None,
    )

    assert result is not None
    assert context["font_path_prefix"] == "./fonts/"
    assert {"DemoEmoji", "DemoSans"}.issubset(set(context["font_files"].keys()))  # type: ignore[index]
    assert (tmp_path / "build" / "fonts" / "DemoSans-Regular.otf").exists()
    assert context["unicode_font_classes"]  # type: ignore[truthy-bool]
    families = {cls["family"] for cls in context["unicode_font_classes"]}  # type: ignore[index]
    assert {"DemoEmoji", "DemoSans"} <= families


def test_kpsewhich_lookup_is_used(monkeypatch, tmp_path: Path) -> None:
    # Emulate kpsewhich returning TeXLive font paths.
    files = {
        "lmroman10-regular.otf": tmp_path / "lmroman10-regular.otf",
        "lmroman10-italic.otf": tmp_path / "lmroman10-italic.otf",
    }
    for path in files.values():
        _write_font(path)

    def fake_kpse(filename: str):
        return files.get(filename)

    monkeypatch.setattr("texsmith.fonts.locator._find_with_kpsewhich", fake_kpse)

    locator = FontLocator()
    located = locator.locate_family("Latin Modern Roman")

    assert located.regular == files["lmroman10-regular.otf"]
    assert located.italic == files["lmroman10-italic.otf"]
