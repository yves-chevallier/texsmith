from __future__ import annotations

from pathlib import Path
import sys

import pytest

from texsmith.adapters.transformers import strategies
from texsmith.core.exceptions import TransformerExecutionError


class _Recorder:
    debug_enabled = False

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        self.warnings.append(message)

    def error(
        self, message: str, exc: BaseException | None = None
    ) -> None:  # pragma: no cover - testing stub
        return

    def event(
        self, name: str, payload: dict[str, object]
    ) -> None:  # pragma: no cover - testing stub
        return


def test_svg_conversion_surfaces_cairo_hint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    emitter = _Recorder()

    class _FakeCairoSvg:
        @staticmethod
        def svg2pdf(*_args, **_kwargs):
            raise OSError('no library called "cairo-2" was found')

    monkeypatch.setitem(sys.modules, "cairosvg", _FakeCairoSvg)
    strategy = strategies.SvgToPdfStrategy()

    with pytest.raises(TransformerExecutionError) as excinfo:
        strategy("<svg></svg>", output_dir=tmp_path, emitter=emitter)

    message = str(excinfo.value).lower()
    assert "cairo" in message
    assert "install" in message
    assert any("cairo" in warning.lower() for warning in emitter.warnings)


def test_playwright_dependency_hint_emits_warning() -> None:
    emitter = _Recorder()
    wrapped = strategies._wrap_playwright_error(
        RuntimeError("Host system is missing dependencies"), emitter=emitter
    )

    assert isinstance(wrapped, TransformerExecutionError)
    message = str(wrapped)
    assert "playwright install-deps" in message
    assert "--diagrams-backend" in message
    assert emitter.warnings
