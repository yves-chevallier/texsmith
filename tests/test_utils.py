import importlib.util

import pytest

from texsmith.adapters.latex.utils import escape_latex_chars


PYLATEXENC_AVAILABLE = importlib.util.find_spec("pylatexenc") is not None


pytestmark = pytest.mark.skipif(not PYLATEXENC_AVAILABLE, reason="pylatexenc not installed")


def test_unicode_characters_preserve_unicode_by_default() -> None:
    payload = "café — 50%"
    escaped = escape_latex_chars(payload)

    assert "café" in escaped
    assert "—" in escaped
    assert "\\%" in escaped


def test_unicode_characters_use_legacy_macros_when_enabled() -> None:
    payload = "café — 50%"
    escaped = escape_latex_chars(payload, legacy_accents=True)

    assert "\\'{e}" in escaped
    assert "\\textemdash" in escaped
    assert "\\%" in escaped
