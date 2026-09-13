from __future__ import annotations

from pathlib import Path
import sys

from emitters import RecordingEmitter
import pytest

from texsmith.adapters.transformers import strategies
from texsmith.core.exceptions import TransformerExecutionError


def test_svg_conversion_surfaces_cairo_hint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, recording_emitter: RecordingEmitter
) -> None:
    emitter = recording_emitter

    class _FakeCairoSvg:
        @staticmethod
        def svg2pdf(*_args, **_kwargs):
            raise OSError('no library called "cairo-2" was found')

    monkeypatch.setitem(sys.modules, "cairosvg", _FakeCairoSvg)
    strategy = strategies.SvgToPdfStrategy()

    with pytest.raises(TransformerExecutionError) as excinfo:
        strategy("<svg></svg>", output_dir=tmp_path, emitter=emitter, backend="local")

    message = str(excinfo.value).lower()
    assert "cairo" in message
    assert "install" in message
    assert any("cairo" in warning.lower() for warning in emitter.warnings)
    assert "transformer-dependency-missing" in emitter.codes()


def test_playwright_dependency_hint_emits_warning(recording_emitter: RecordingEmitter) -> None:
    emitter = recording_emitter
    wrapped = strategies._wrap_playwright_error(
        RuntimeError("Host system is missing dependencies"), emitter=emitter
    )

    assert isinstance(wrapped, TransformerExecutionError)
    message = str(wrapped)
    assert "playwright install-deps" in message
    assert "--diagrams-backend" in message
    assert emitter.warnings
    assert emitter.codes() == ["transformer-dependency-missing"]
