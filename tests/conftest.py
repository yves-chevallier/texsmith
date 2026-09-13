"""Fixtures shared by the test suite."""

from __future__ import annotations

from emitters import RecordingEmitter
import pytest


@pytest.fixture
def recording_emitter() -> RecordingEmitter:
    """An emitter that keeps every record it is shown."""
    return RecordingEmitter()
