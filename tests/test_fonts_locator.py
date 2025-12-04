import io
from pathlib import Path
import zipfile

from texsmith.core.diagnostics import NullEmitter
from texsmith.fonts.locator import FontLocator
from texsmith.fonts.manager import prepare_fonts_for_context
from texsmith.fonts.matcher import FontMatchResult, match_text


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
    emoji_spec = context["emoji_spec"]  # type: ignore[index]
    emoji_family = emoji_spec["font_family"]
    assert emoji_family
    assert emoji_family in context["font_files"]  # type: ignore[index]
    assert context["unicode_font_classes"]  # type: ignore[truthy-bool]
    families = {cls["family"] for cls in context["unicode_font_classes"]}  # type: ignore[index]
    assert emoji_family in families
    ranges = {tuple(pair) for cls in context["unicode_font_classes"] for pair in cls["ranges"]}  # type: ignore[index]
    assert all(int(start, 16) >= 0x80 for start, _ in ranges)
    assert emoji_spec["font_family"] == "OpenMoji Black"
    assert emoji_spec["mode"] == "black"


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


def _openmoji_zip_payload() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("OpenMoji-black-glyf/OpenMoji-black-glyf.ttf", b"demo")
    return buffer.getvalue()


def _emoji_match_result() -> FontMatchResult:
    return FontMatchResult(
        fallback_fonts=("OpenMoji Black",),
        present_fonts=(),
        missing_fonts=("OpenMoji Black",),
        missing_codepoints=(0x1F600,),
        font_ranges={"OpenMoji Black": ["U+1F600"]},
        fonts_yaml=None,
        script_blocks={},
    )


def test_prepare_fonts_downloads_emoji_font(monkeypatch, tmp_path: Path) -> None:
    payload = _openmoji_zip_payload()

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()
            return False

    def fake_open(url: str, timeout: int = 30):
        return FakeResponse(payload)

    monkeypatch.setenv("TEXSMITH_FONT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr("texsmith.fonts.cache._open_url", fake_open)

    match = _emoji_match_result()
    context: dict[str, object] = {}
    locator = FontLocator()

    result = prepare_fonts_for_context(
        template_context=context,
        output_dir=tmp_path / "build",
        font_match=match,
        font_locator=locator,
        emitter=NullEmitter(),
    )

    assert result is not None
    cached_fonts = list((tmp_path / "cache").rglob("OpenMoji-black-glyf.ttf"))
    assert cached_fonts
    assert "OpenMoji Black" in context["font_files"]  # type: ignore[index]
    assert "OpenMoji Black" in context["fallback_fonts"]  # type: ignore[index]
    emoji_spec = context["emoji_spec"]  # type: ignore[index]
    assert emoji_spec["font_family"] == "OpenMoji Black"


def test_prepare_fonts_falls_back_to_twemoji(monkeypatch, tmp_path: Path) -> None:
    def fake_open(url: str, timeout: int = 30):
        raise OSError("offline")

    monkeypatch.setenv("TEXSMITH_FONT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr("texsmith.fonts.cache._open_url", fake_open)

    class ListEmitter(NullEmitter):
        def __init__(self) -> None:
            self.messages: list[str] = []

        def warning(self, message: str, exc: BaseException | None = None) -> None:  # type: ignore[override]
            self.messages.append(message)

    emitter = ListEmitter()
    match = _emoji_match_result()
    context: dict[str, object] = {}
    locator = FontLocator()

    result = prepare_fonts_for_context(
        template_context=context,
        output_dir=tmp_path / "build",
        font_match=match,
        font_locator=locator,
        emitter=emitter,
    )

    assert result is not None
    assert context.get("emoji_mode") == "artifact"
    emoji_spec = context["emoji_spec"]  # type: ignore[index]
    assert emoji_spec["mode"] == "artifact"
    assert "OpenMoji Black" not in context["fallback_fonts"]  # type: ignore[index]
    assert any("Emoji font" in msg for msg in emitter.messages)
