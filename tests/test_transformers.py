from __future__ import annotations

import base64
from pathlib import Path

import pytest
import requests

from texsmith.adapters.transformers import fetch_image
from texsmith.core.http import DEFAULT_USER_AGENT


def test_fetch_image_sets_user_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured_headers: dict[str, str] = {}

    class DummyResponse:
        def __init__(self) -> None:
            self.headers = {"Content-Type": "image/png"}
            self.content = base64.b64decode(
                b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAOm/pUUAAAAASUVORK5CYII="
            )
            self.ok = True

    def fake_get(
        url: str, *, timeout: float, headers: dict[str, str] | None = None
    ) -> DummyResponse:
        captured_headers.update(headers or {})
        return DummyResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    destination = fetch_image(
        "https://example.com/demo.png", output_dir=tmp_path, user_agent="custom-agent/1.0"
    )

    assert destination.exists()
    assert captured_headers.get("User-Agent") == "custom-agent/1.0"


def test_fetch_image_identifies_texsmith_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No caller-supplied agent: one honest identifier, not a spoofed browser."""
    captured_headers: dict[str, str] = {}

    class DummyResponse:
        def __init__(self) -> None:
            self.headers = {"Content-Type": "image/png"}
            self.content = base64.b64decode(
                b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAOm/pUUAAAAASUVORK5CYII="
            )
            self.ok = True

    def fake_get(
        url: str, *, timeout: float, headers: dict[str, str] | None = None
    ) -> DummyResponse:
        captured_headers.update(headers or {})
        return DummyResponse()

    monkeypatch.setattr(requests, "get", fake_get)
    fetch_image("https://example.com/other.png", output_dir=tmp_path)

    assert captured_headers.get("User-Agent") == DEFAULT_USER_AGENT
