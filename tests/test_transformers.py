from __future__ import annotations

import base64
from pathlib import Path

import pytest
import requests

from texsmith.adapters.transformers import fetch_image


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

    monkeypatch.setenv("TEXSMITH_HTTP_USER_AGENT", "custom-agent/1.0")
    monkeypatch.setattr(requests, "get", fake_get)

    destination = fetch_image("https://example.com/demo.png", output_dir=tmp_path)

    assert destination.exists()
    assert captured_headers.get("User-Agent") == "custom-agent/1.0"
