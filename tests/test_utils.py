import importlib.util

import pytest

from texsmith.utils import escape_latex_chars


PYLATEXENC_AVAILABLE = importlib.util.find_spec("pylatexenc") is not None


pytestmark = pytest.mark.skipif(not PYLATEXENC_AVAILABLE, reason="pylatexenc not installed")


def test_unicode_characters_are_encoded() -> None:
    payload = "café — 50%"
    escaped = escape_latex_chars(payload)

    assert "\\'{e}" in escaped
    assert "\\textemdash" in escaped
    assert "\\%" in escaped
