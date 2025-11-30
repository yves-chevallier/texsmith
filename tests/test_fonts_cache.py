from __future__ import annotations

import io
import json
from pathlib import Path
import zipfile

from texsmith.fonts import cache
from texsmith.fonts.registry import FontSourceSpec


def _make_spec(url: str, **kwargs) -> FontSourceSpec:
    return FontSourceSpec(
        id=kwargs.get("id", "test:font"),
        family=kwargs.get("family", "Test Family"),
        style=kwargs.get("style", "regular"),
        url=url,
        filename=kwargs.get("filename", "Test.otf"),
        version=kwargs.get("version", "test"),
        zip_member=kwargs.get("zip_member"),
        alt_members=kwargs.get("alt_members", ()),
        scripts=kwargs.get("scripts", ("latin",)),
        blocks=kwargs.get("blocks", ("Basic Latin",)),
    )


def test_ensure_font_downloads_and_reuses_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv(cache.FONT_CACHE_DIR_ENV, str(tmp_path))
    calls: list[str] = []

    def fake_download(url: str, _emitter):
        calls.append(url)
        return b"dummy-font"

    monkeypatch.setattr(cache, "_download_url", fake_download)
    spec = _make_spec("https://example.com/font.otf")

    record = cache.ensure_font(spec)
    assert record is not None
    assert record.path.exists()
    metadata_path = cache.font_cache_dir() / spec.cache_key / cache.METADATA_FILENAME
    assert json.loads(metadata_path.read_text()).get("schema") == cache.CACHE_SCHEMA_VERSION
    # second call should reuse metadata and skip download
    record_again = cache.ensure_font(spec)
    assert record_again is not None
    assert calls == ["https://example.com/font.otf"]


def test_ensure_font_extracts_from_zip(tmp_path, monkeypatch):
    monkeypatch.setenv(cache.FONT_CACHE_DIR_ENV, str(tmp_path))
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as zf:
        zf.writestr("fonts/Example.otf", b"zip-font")

    def fake_download(url: str, _emitter):
        assert url == "https://example.com/zip.zip"
        return payload.getvalue()

    monkeypatch.setattr(cache, "_download_url", fake_download)
    spec = _make_spec(
        "https://example.com/zip.zip",
        filename="Example.otf",
        zip_member="fonts/Example.otf",
        alt_members=("Example.otf",),
    )
    record = cache.ensure_font(spec)
    assert record is not None
    assert record.path.read_bytes() == b"zip-font"


def test_cache_fonts_for_families_uses_registry(tmp_path, monkeypatch):
    monkeypatch.setenv(cache.FONT_CACHE_DIR_ENV, str(tmp_path))
    payload = b"family-font"

    def fake_download(url: str, _emitter):
        return payload

    monkeypatch.setattr(cache, "_download_url", fake_download)
    specs = (_make_spec("https://example.com/family.otf", family="Family A"),)
    monkeypatch.setattr(
        cache, "sources_for_family", lambda family: specs if family == "Family A" else ()
    )

    cached, failures = cache.cache_fonts_for_families(["Family A", "Unknown"])
    assert "Family A" in cached
    assert failures == set()
    path = cached["Family A"]
    assert isinstance(path, Path)
    assert path.read_bytes() == payload
