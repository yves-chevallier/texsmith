from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from texsmith.adapters.plugins import snippet


def _build_block(content: str = "print('Hello')") -> snippet.SnippetBlock:
    overrides: dict[str, str] = {}
    digest = snippet._hash_payload(
        content,
        overrides,
        cwd=None,
        template_id=None,
        layout=None,
        sources=[],
        promote_title=True,
        drop_title=False,
        suppress_title=False,
    )
    return snippet.SnippetBlock(
        content=content,
        front_matter={},
        sources=[],
        layout=None,
        preview_dogear=False,
        template_id=None,
        cwd=None,
        caption=None,
        label=None,
        figure_width=None,
        template_overrides=overrides,
        digest=digest,
        bibliography_files=[],
        promote_title=True,
        drop_title=False,
        suppress_title_metadata=False,
    )


def test_ensure_snippet_assets_reuses_cached_artifacts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TEXSMITH_CACHE_DIR", str(tmp_path / "cache-root"))
    monkeypatch.setattr(snippet, "_SNIPPET_CACHE", None, raising=False)
    block = _build_block()

    cache = snippet._resolve_cache()
    assert cache is not None

    pdf_source = tmp_path / "prefill.pdf"
    png_source = tmp_path / "prefill.png"
    pdf_source.write_bytes(b"%PDF-TEST%")
    png_source.write_bytes(b"\x89PNG\r\n")
    cache.store(block.digest, pdf_source, png_source, template_version=None)
    cache.flush()

    compile_called = {"value": False}

    def _fail_compile(*_args, **_kwargs) -> Path:
        compile_called["value"] = True
        raise AssertionError("Snippet compilation should be skipped when cached assets exist.")

    monkeypatch.setattr(snippet, "_compile_pdf", _fail_compile)

    destination = tmp_path / "snippets"
    assets = snippet.ensure_snippet_assets(
        block,
        output_dir=destination,
    )

    assert assets.pdf.read_bytes() == pdf_source.read_bytes()
    assert assets.png.read_bytes() == png_source.read_bytes()
    assert compile_called["value"] is False


def test_cache_store_records_markdown_and_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TEXSMITH_CACHE_DIR", str(tmp_path / "cache-root"))
    monkeypatch.setattr(snippet, "_SNIPPET_CACHE", None, raising=False)
    block = _build_block("body")
    cache = snippet._resolve_cache()
    assert cache is not None

    pdf_source = tmp_path / "prefill.pdf"
    png_source = tmp_path / "prefill.png"
    pdf_source.write_bytes(b"%PDF-TEST%")
    png_source.write_bytes(b"\x89PNG\r\n")
    source_path = tmp_path / "docs" / "host.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("host", encoding="utf-8")

    cache.store(
        block.digest,
        pdf_source,
        png_source,
        template_version="v1",
        block=block,
        source_path=source_path,
    )

    entry = cache.metadata["entries"][block.digest]
    md_name = entry["files"].get("md")
    md_path = cache.root / md_name
    assert md_path.exists()
    assert md_path.read_text(encoding="utf-8") == block.content
    assert entry["source"] == str(source_path)
    assert entry["attributes"]["figure_width"] is None
    assert entry["attributes"]["layout"] is None
    assert entry["files"]["pdf"] == snippet.asset_filename(block.digest, ".pdf")
    assert (cache.root / entry["files"]["pdf"]).read_bytes() == pdf_source.read_bytes()


def test_the_shared_cache_is_filled_through_a_name_of_its_own(tmp_path, monkeypatch) -> None:
    """Several renders share one cache: an entry appears whole or not at all."""
    monkeypatch.setenv("TEXSMITH_CACHE_DIR", str(tmp_path / "cache-root"))
    monkeypatch.setattr(snippet, "_SNIPPET_CACHE", None, raising=False)
    block = _build_block("body")
    cache = snippet._resolve_cache()
    assert cache is not None

    pdf_source = tmp_path / "prefill.pdf"
    png_source = tmp_path / "prefill.png"
    pdf_source.write_bytes(b"%PDF-TEST%")
    png_source.write_bytes(b"\x89PNG\r\n")

    cache.store(block.digest, pdf_source, png_source, template_version="v1", block=block)
    cache.flush()

    # The temporary names carry the process id, so two writers never share one,
    # and none of them is left behind.
    assert snippet._cache_tmp_path(cache.metadata_path).name.endswith(f"{os.getpid()}.tmp")
    assert [path.name for path in cache.root.glob("*.tmp")] == []
    assert json.loads(cache.metadata_path.read_text(encoding="utf-8"))["entries"]


def test_a_failed_cache_write_leaves_the_previous_entry_alone(tmp_path) -> None:
    target = tmp_path / "entry.json"
    target.write_text("kept", encoding="utf-8")

    def _explode(path) -> None:
        path.write_text("half", encoding="utf-8")
        raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        snippet._publish_into_cache(target, _explode)

    assert target.read_text(encoding="utf-8") == "kept"
    assert [path.name for path in tmp_path.glob("*.tmp")] == []
